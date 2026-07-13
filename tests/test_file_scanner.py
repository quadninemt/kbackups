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


if __name__ == "__main__":
    unittest.main()
