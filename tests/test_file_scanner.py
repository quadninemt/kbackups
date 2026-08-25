import os
import unittest
import tempfile
import shutil
from unittest.mock import patch
from src.file_scanner import FileScanner


class TestReservedNames(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()

    def test_bare_reserved_names(self):
        for name in ("nul", "con", "prn", "aux", "com1", "com9",
                     "lpt1", "lpt9", "NUL", "Com3"):
            self.assertTrue(self.scanner._is_reserved_name(name),
                            f"{name} should be reserved")

    def test_reserved_with_extension(self):
        # On Windows 'nul.txt' still resolves to the nul device.
        self.assertTrue(self.scanner._is_reserved_name("nul.txt"))
        self.assertTrue(self.scanner._is_reserved_name("CON.log"))

    def test_normal_names_not_reserved(self):
        for name in ("report.txt", "nullable.dat", "console.js",
                     "com.txt", "lpt.md", "auxiliary.png"):
            self.assertFalse(self.scanner._is_reserved_name(name),
                             f"{name} should NOT be reserved")


class TestScanResilience(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()
        self.tmp = tempfile.mkdtemp(prefix="kbtest_")
        with open(os.path.join(self.tmp, "good.txt"), "w") as f:
            f.write("data")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reserved_file_skipped_no_crash(self):
        # Simulate a directory listing that includes reserved device names.
        # A real 'nul' file would make os.path.relpath raise ValueError and
        # (before the fix) kill the whole scan.
        walk_result = [(self.tmp, [], ["good.txt", "nul", "con.log"])]
        with patch("os.walk", return_value=walk_result):
            result = self.scanner.scan([self.tmp])
        names = [os.path.basename(r["path"]) for r in result]
        self.assertEqual(names, ["good.txt"])

    def test_valueerror_on_file_does_not_abort_scan(self):
        # Any non-reserved path that still trips relpath's mount check must be
        # logged and skipped, not propagated.
        with open(os.path.join(self.tmp, "second.txt"), "w") as f:
            f.write("more")

        real_relpath = os.path.relpath

        def flaky_relpath(path, start):
            if os.path.basename(path) == "good.txt":
                raise ValueError("path is on mount '\\\\.\\x', start on mount 'C:'")
            return real_relpath(path, start)

        with patch("os.path.relpath", side_effect=flaky_relpath):
            result = self.scanner.scan([self.tmp])
        names = sorted(os.path.basename(r["path"]) for r in result)
        self.assertEqual(names, ["second.txt"])


class TestDefaultExcludes(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()
        self.tmp = tempfile.mkdtemp(prefix="kbtest_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, *parts):
        path = os.path.join(self.tmp, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("x")

    def test_electron_cache_dirs_excluded_by_default(self):
        # No exclude patterns passed at all — the defaults must still apply.
        self._make("keep.txt")
        self._make("GPUCache", "data_0")
        self._make("Cache", "Cache_Data", "index")
        self._make("nested", "CachedData", "blob.js")

        result = self.scanner.scan([self.tmp])
        names = sorted(os.path.basename(r["path"]) for r in result)
        self.assertEqual(names, ["keep.txt"])

    def test_job_excludes_add_to_defaults(self):
        self._make("keep.txt")
        self._make("notes.tmp")
        self._make("GPUCache", "data_0")

        result = self.scanner.scan([self.tmp], ["*.tmp"])
        names = sorted(os.path.basename(r["path"]) for r in result)
        self.assertEqual(names, ["keep.txt"])

    def test_similar_user_folder_names_not_excluded(self):
        # 'Cached' and 'Crash Reports' must survive — only exact artefact names go.
        self._make("Cached", "invoice.pdf")
        self._make("Crash Reports", "notes.md")

        result = self.scanner.scan([self.tmp])
        names = sorted(os.path.basename(r["path"]) for r in result)
        self.assertEqual(names, ["invoice.pdf", "notes.md"])


class TestFileSources(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()
        self.tmp = tempfile.mkdtemp(prefix="kbtest_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, name, content="x"):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_single_file_source_is_scanned(self):
        # A file as a source path used to silently back up nothing.
        target = self._make(".claude.json", "{}")
        result = self.scanner.scan([target])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], os.path.abspath(target))

    def test_single_file_source_rel_path_is_bare_name(self):
        # rel_path must be the file name so it mirrors to the destination root,
        # not into a folder named after the file.
        target = self._make(".claude.json", "{}")
        result = self.scanner.scan([target])
        self.assertEqual(result[0]["rel_path"], ".claude.json")

    def test_file_and_directory_sources_together(self):
        self._make(os.path.join("tree", "inner.txt"))
        target = self._make("loose.json", "{}")
        result = self.scanner.scan([os.path.join(self.tmp, "tree"), target])
        names = sorted(os.path.basename(r["path"]) for r in result)
        self.assertEqual(names, ["inner.txt", "loose.json"])

    def test_excluded_file_source_is_skipped(self):
        target = self._make("secrets.json", "{}")
        self.assertEqual(self.scanner.scan([target], ["secrets.json"]), [])

    def test_empty_source_is_warned_not_silent(self):
        os.makedirs(os.path.join(self.tmp, "empty"))
        with self.assertLogs("src.file_scanner", level="WARNING") as captured:
            result = self.scanner.scan([os.path.join(self.tmp, "empty")])
        self.assertEqual(result, [])
        self.assertTrue(any("contributed 0 files" in m for m in captured.output))

    def test_source_fully_excluded_is_warned(self):
        # An exclude pattern that swallows everything must not look like success.
        self._make(os.path.join("tree", "notes.tmp"))
        with self.assertLogs("src.file_scanner", level="WARNING") as captured:
            self.scanner.scan([os.path.join(self.tmp, "tree")], ["*.tmp"])
        self.assertTrue(any("contributed 0 files" in m for m in captured.output))


if __name__ == "__main__":
    unittest.main()
