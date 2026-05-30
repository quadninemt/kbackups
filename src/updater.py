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

        bat_path = os.path.join(tempfile.gettempdir(), "k_backups_apply_update.bat")
        bat = (
            "@echo off\n"
            ":waitloop\n"
            f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul\n'
            "if not errorlevel 1 (\n"
            "    timeout /t 1 /nobreak >nul\n"
            "    goto waitloop\n"
            ")\n"
            f'robocopy "{extract_dir}" "{app_dir}" /E /IS /IT /NP /NJH /NJS\n'
            f'start "" "{app_exe}"\n'
            f'rmdir /S /Q "{extract_dir}" >nul 2>&1\n'
            'del "%~f0"\n'
        )

        try:
            with open(bat_path, "w") as f:
                f.write(bat)

            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            self.logger.info("Update helper launched: %s", bat_path)
            return True

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
