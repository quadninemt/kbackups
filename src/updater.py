import json
import logging
import os
import subprocess
import sys
import tempfile
import zipfile
import urllib.request
import urllib.error

GITHUB_REPO = "quadninemt/kbackups"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class Updater:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_for_update(self, current_version):
        """
        Query GitHub Releases for the latest version.
        Returns (latest_version_str, download_url) if a newer release with a
        ZIP asset exists, or None if up to date or the check fails.
        """
        try:
            req = urllib.request.Request(
                API_URL,
                headers={"User-Agent": "k_backups-updater"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            tag = data.get("tag_name", "")
            if not tag or not self._is_newer(tag, current_version):
                return None

            zip_url = next(
                (a["browser_download_url"] for a in data.get("assets", [])
                 if a.get("name", "").endswith(".zip")),
                None
            )
            if not zip_url:
                self.logger.warning("Release %s found but has no ZIP asset.", tag)
                return None

            return (tag.lstrip("v"), zip_url)

        except Exception as e:
            self.logger.warning("Update check failed: %s", e)
            return None

    def download_update(self, url, progress_callback=None):
        """
        Download the release ZIP to a temp file.
        Returns the local path to the ZIP, or None on failure.
        """
        try:
            zip_path = os.path.join(tempfile.gettempdir(), "k_backups_update.zip")
            if progress_callback:
                progress_callback(0, 0, "Connecting to update server...")

            req = urllib.request.Request(url, headers={"User-Agent": "k_backups-updater"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(zip_path, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            mb_done = downloaded / 1048576
                            mb_total = total / 1048576
                            progress_callback(
                                downloaded, total,
                                f"Downloading update: {mb_done:.1f} / {mb_total:.1f} MB"
                            )

            self.logger.info("Update downloaded to %s", zip_path)
            return zip_path

        except Exception as e:
            self.logger.error("Failed to download update: %s", e, exc_info=True)
            return None

    def apply_update(self, zip_path):
        """
        Extract the ZIP to a temp directory, write a helper .bat that:
          1. Waits for the current process to exit
          2. Copies new files over the app directory (robocopy)
          3. Relaunches the app
          4. Deletes itself and the temp extract dir

        Returns True and launches the helper (caller must then call self.destroy()).
        Returns False if the app is not frozen or extraction fails.
        """
        if not getattr(sys, "frozen", False):
            self.logger.warning("apply_update called outside a packaged app — skipping.")
            return False

        app_dir = os.path.dirname(sys.executable)
        app_exe = sys.executable
        pid = os.getpid()

        try:
            extract_dir = tempfile.mkdtemp(prefix="k_backups_upd_")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            self.logger.info("Extracted update to %s", extract_dir)
        except Exception as e:
            self.logger.error("Failed to extract update ZIP: %s", e, exc_info=True)
            return False

        exe_name = os.path.basename(app_exe)
        bat_path = os.path.join(tempfile.gettempdir(), "k_backups_apply_update.bat")
        log_path = os.path.join(app_dir, "update_helper.log")

        # Robust helper:
        #  - waits for the running app (by PID *and* image name) to fully exit
        #  - copies with LIMITED robocopy retries (/R:5 /W:2) so it can never
        #    hang forever if the exe is briefly locked or AV-blocked
        #  - logs every step (incl. robocopy exit code) to update_helper.log
        #  - on copy failure, retains the old version and still relaunches so
        #    the user is never left without a working app
        # NOTE: every redirection has a SPACE before > / >> on purpose. A token
        # like "%RC%>>" where RC is a digit would otherwise be parsed by cmd as a
        # stream-handle redirection (e.g. "1>>"), silently eating the value.
        bat = (
            "@echo off\n"
            f'set "LOG={log_path}"\n'
            'echo [update] started %DATE% %TIME% > "%LOG%"\n'
            f'echo [update] waiting for {exe_name} (PID {pid}) to exit >> "%LOG%"\n'
            ":waitloop\n"
            f'tasklist /FI "PID eq {pid}" /NH 2>nul | find /I "{exe_name}" >nul\n'
            "if %errorlevel%==0 (\n"
            # ping, not timeout: a detached/no-console helper has no stdin, and
            # `timeout` aborts immediately ("input redirection is not supported").
            "    ping -n 2 127.0.0.1 >nul\n"
            "    goto waitloop\n"
            ")\n"
            'echo [update] app exited; pausing briefly >> "%LOG%"\n'
            "ping -n 3 127.0.0.1 >nul\n"
            f'echo [update] copying new files into "{app_dir}" >> "%LOG%"\n'
            f'robocopy "{extract_dir}" "{app_dir}" /E /IS /IT /R:5 /W:2 /NP /NJH /NJS >> "%LOG%" 2>&1\n'
            "set RC=%errorlevel%\n"
            'echo [update] robocopy exit code %RC% >> "%LOG%"\n'
            "if %RC% geq 8 (\n"
            '    echo [update] COPY FAILED - old version retained. Check antivirus ^(Avast^) is not blocking writes to this folder. >> "%LOG%"\n'
            ") else (\n"
            '    echo [update] copy succeeded - update applied >> "%LOG%"\n'
            ")\n"
            'echo [update] relaunching app >> "%LOG%"\n'
            f'start "" "{app_exe}"\n'
            f'rmdir /S /Q "{extract_dir}" >nul 2>&1\n'
            'echo [update] done %DATE% %TIME% >> "%LOG%"\n'
            'del "%~f0"\n'
        )

        try:
            with open(bat_path, "w") as f:
                f.write(bat)

            # The helper MUST outlive this app's exit. Apps started via Explorer
            # or a launcher often run inside a Job Object with kill-on-close, which
            # also kills a merely-"detached" child — that silently killed the
            # previous helper mid-wait. CREATE_BREAKAWAY_FROM_JOB escapes that job.
            # It raises ERROR_ACCESS_DENIED when the process is NOT in a job (or the
            # job forbids breakaway), so try it first and fall back without it.
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            CREATE_BREAKAWAY_FROM_JOB = 0x01000000
            base_flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

            launched = False
            for extra in (CREATE_BREAKAWAY_FROM_JOB, 0):
                try:
                    subprocess.Popen(
                        ["cmd.exe", "/c", bat_path],
                        cwd=tempfile.gettempdir(),
                        creationflags=base_flags | extra,
                        close_fds=True,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    self.logger.info("Update helper launched (breakaway=%s): %s (log: %s)",
                                     bool(extra), bat_path, log_path)
                    break
                except OSError as e:
                    self.logger.warning("Helper launch with flags 0x%X failed: %s", base_flags | extra, e)
                    continue

            return launched

        except Exception as e:
            self.logger.error("Failed to launch update helper: %s", e, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_newer(remote_tag, local_version):
        def parse(v):
            return tuple(int(x) for x in v.lstrip("v").split("."))
        try:
            return parse(remote_tag) > parse(local_version)
        except (ValueError, AttributeError):
            return False
