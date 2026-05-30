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


if __name__ == '__main__':
    unittest.main()
