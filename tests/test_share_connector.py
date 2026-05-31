import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from src.share_connector import ShareConnector, LocalConnector


class TestShareConnector(unittest.TestCase):
    @patch('smbclient.register_session')
    @patch('smbclient.listdir')
    def test_connect_success(self, mock_listdir, mock_register):
        connector = ShareConnector(r"\\Server\Share", "user", "pass")
        mock_listdir.return_value = []
        result = connector.connect()
        self.assertTrue(result)
        mock_register.assert_called_with("Server", username="user", password="pass")

    @patch('smbclient.register_session')
    def test_connect_failure(self, mock_register):
        connector = ShareConnector(r"\\Server\Share", "user", "pass")
        mock_register.side_effect = Exception("Connection Failed")
        result = connector.connect()
        self.assertFalse(result)

    @patch('smbclient.scandir')
    def test_list_files(self, mock_scandir):
        connector = ShareConnector(r"\\Server\Share", "user", "pass")
        entry1 = MagicMock()
        entry1.is_file.return_value = True
        entry1.name = "file1.txt"
        entry1.stat.return_value.st_size = 100
        entry1.stat.return_value.st_mtime = 12345
        entry2 = MagicMock()
        entry2.is_file.return_value = False
        mock_scandir.return_value = [entry1, entry2]
        files = list(connector.list_files(""))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], ("file1.txt", 100, 12345))


class TestLocalConnector(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_connect_always_succeeds(self):
        self.assertTrue(LocalConnector().connect())

    def test_upload_creates_file_and_directories(self):
        src = os.path.join(self.tmpdir, "source.txt")
        dst = os.path.join(self.tmpdir, "sub", "dest.txt")
        with open(src, 'w') as f:
            f.write("hello")
        connector = LocalConnector()
        self.assertTrue(connector.upload_file(src, dst))
        self.assertTrue(os.path.exists(dst))
        with open(dst) as f:
            self.assertEqual(f.read(), "hello")

    def test_download_creates_file_and_directories(self):
        src = os.path.join(self.tmpdir, "remote.txt")
        dst = os.path.join(self.tmpdir, "local", "copy.txt")
        with open(src, 'w') as f:
            f.write("world")
        connector = LocalConnector()
        self.assertTrue(connector.download_file(src, dst))
        self.assertTrue(os.path.exists(dst))

    def test_delete_file(self):
        path = os.path.join(self.tmpdir, "todelete.txt")
        with open(path, 'w') as f:
            f.write("x")
        connector = LocalConnector()
        self.assertTrue(connector.delete_file(path))
        self.assertFalse(os.path.exists(path))

    def test_delete_missing_file_returns_true(self):
        connector = LocalConnector()
        self.assertTrue(connector.delete_file(os.path.join(self.tmpdir, "nonexistent.txt")))

    def test_path_exists(self):
        connector = LocalConnector()
        self.assertTrue(connector.path_exists(self.tmpdir))
        self.assertFalse(connector.path_exists(os.path.join(self.tmpdir, "nope")))

    def test_create_directory(self):
        new_dir = os.path.join(self.tmpdir, "a", "b", "c")
        connector = LocalConnector()
        self.assertTrue(connector.create_directory(new_dir))
        self.assertTrue(os.path.isdir(new_dir))

    def test_list_files(self):
        f1 = os.path.join(self.tmpdir, "file1.txt")
        f2 = os.path.join(self.tmpdir, "file2.txt")
        os.makedirs(os.path.join(self.tmpdir, "subdir"))
        open(f1, 'w').close()
        open(f2, 'w').close()
        connector = LocalConnector()
        names = [name for name, _, _ in connector.list_files(self.tmpdir)]
        self.assertIn("file1.txt", names)
        self.assertIn("file2.txt", names)
        self.assertNotIn("subdir", names)


class TestBackupEngineRetry(unittest.TestCase):
    def _make_engine(self):
        from src.backup_engine import BackupEngine
        engine = BackupEngine(MagicMock())
        engine.RETRY_BACKOFF_SECONDS = 0  # no sleep in tests
        return engine

    def _meta(self, path, rel, placeholder=False):
        return {'path': path, 'rel_path': rel, 'size': 1, 'mtime': 1.0,
                'is_placeholder': placeholder}

    def test_upload_one_success(self):
        engine = self._make_engine()
        connector = MagicMock()
        connector.upload_file.return_value = True
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 10
            mock_stat.return_value.st_mtime = 123.0
            ok, payload = engine._upload_one(connector, self._meta(r"C:\a.txt", "a.txt"), "dest")
        self.assertTrue(ok)
        self.assertEqual(payload, (r"C:\a.txt", "a.txt", 10, 123.0))

    def test_upload_one_failure(self):
        engine = self._make_engine()
        connector = MagicMock()
        connector.upload_file.return_value = False
        ok, payload = engine._upload_one(connector, self._meta(r"C:\a.txt", "a.txt"), "dest")
        self.assertFalse(ok)
        self.assertEqual(payload, "upload failed")

    def test_upload_one_hydration_failure(self):
        engine = self._make_engine()
        connector = MagicMock()
        engine.file_scanner = MagicMock()
        engine.file_scanner.hydrate_file.return_value = False
        ok, payload = engine._upload_one(connector, self._meta(r"C:\a.txt", "a.txt", placeholder=True), "dest")
        self.assertFalse(ok)
        self.assertEqual(payload, "hydration failed")
        connector.upload_file.assert_not_called()

    def test_retry_eventually_succeeds(self):
        """A file that fails twice then succeeds should not be a persistent failure."""
        engine = self._make_engine()
        connector = MagicMock()
        # Fail, fail, succeed across the 3 attempts (1 initial + 2 retries)
        connector.upload_file.side_effect = [False, False, True]
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 1
            mock_stat.return_value.st_mtime = 1.0
            # Simulate the engine's retry loop directly via _upload_one calls
            meta = self._meta(r"C:\flaky.txt", "flaky.txt")
            results = [engine._upload_one(connector, meta, "dest")[0] for _ in range(3)]
        self.assertEqual(results, [False, False, True])

    def test_run_job_records_persistent_failure(self):
        """End-to-end: a permanently failing upload is recorded in last_run_failures."""
        engine = self._make_engine()
        cfg = engine.config_manager
        cfg.get_jobs.return_value = [{
            'name': 'job1',
            'source_paths': [r'C:\src'],
            'exclude_patterns': [],
            'destination_path': r'E:\backup',  # local dest → LocalConnector
        }]
        cfg.get_nas_settings.return_value = {}

        engine.file_scanner = MagicMock()
        engine.file_scanner.scan.return_value = [
            {'path': r'C:\src\good.txt', 'rel_path': 'good.txt', 'size': 1, 'mtime': 1.0, 'is_placeholder': False},
            {'path': r'C:\src\bad.txt', 'rel_path': 'bad.txt', 'size': 1, 'mtime': 1.0, 'is_placeholder': False},
        ]
        engine.manifest_manager = MagicMock()
        engine.manifest_manager.get_job_files.return_value = {}

        # Mock the LocalConnector created inside run_job
        fake_conn = MagicMock()
        fake_conn.connect.return_value = True
        fake_conn.path_exists.return_value = True
        # good.txt uploads ok; bad.txt always fails

        def upload_side_effect(local, remote):
            return not local.endswith('bad.txt')
        fake_conn.upload_file.side_effect = upload_side_effect

        with patch.object(engine, '_create_connector', return_value=fake_conn), \
             patch.object(engine, '_upload_job_snapshot', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 1
            mock_stat.return_value.st_mtime = 1.0
            result = engine.run_job('job1')

        self.assertTrue(result)  # job ran to completion
        self.assertEqual(len(engine.last_run_failures), 1)
        self.assertEqual(engine.last_run_failures[0]['path'], r'C:\src\bad.txt')
        self.assertIn('error', engine.last_run_failures[0])
        # bad.txt attempted 1 + MAX_UPLOAD_RETRIES times
        bad_attempts = sum(1 for c in fake_conn.upload_file.call_args_list if c.args[0].endswith('bad.txt'))
        self.assertEqual(bad_attempts, 1 + engine.MAX_UPLOAD_RETRIES)


class TestFileScannerProgress(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_reports_progress(self):
        from src.file_scanner import FileScanner
        for i in range(5):
            with open(os.path.join(self.tmpdir, f"f{i}.txt"), "w") as f:
                f.write("x")
        scanner = FileScanner()
        scanner.SCAN_PROGRESS_INTERVAL = 2  # fire often for the test
        counts = []
        files = scanner.scan([self.tmpdir], progress_callback=lambda c: counts.append(c))
        self.assertEqual(len(files), 5)
        # callback should have fired at multiples of 2 (2 and 4)
        self.assertTrue(len(counts) >= 2)
        self.assertTrue(all(c % 2 == 0 for c in counts))

    def test_scan_without_callback_still_works(self):
        from src.file_scanner import FileScanner
        with open(os.path.join(self.tmpdir, "a.txt"), "w") as f:
            f.write("x")
        files = FileScanner().scan([self.tmpdir])
        self.assertEqual(len(files), 1)


if __name__ == '__main__':
    unittest.main()
