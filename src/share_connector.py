import smbclient
import os
import shutil
import stat
import logging


class LocalConnector:
    """Connector for local and USB/external drive destinations."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._connected = False

    def connect(self):
        self._connected = True
        self.logger.info("LocalConnector: using local filesystem.")
        return True

    def disconnect(self):
        self._connected = False

    @staticmethod
    def _clear_readonly(path):
        """
        Drop the read-only attribute from an existing destination file so it can
        be overwritten. Git object files are created mode 444, which otherwise
        makes the copy fail with PermissionError on every run.
        """
        try:
            if os.path.exists(path) and not os.access(path, os.W_OK):
                os.chmod(path, stat.S_IWRITE)
        except OSError:
            # Best effort — if this fails the copy below reports the real error.
            pass

    def _copy(self, src, dst):
        """
        Copy src to dst, creating parent directories. File data is required;
        metadata (timestamps, mode) is best effort.
        """
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            self._clear_readonly(dst)
            shutil.copyfile(src, dst)
        except Exception as e:
            self.logger.error("Failed to copy %s to %s: %s", src, dst, e, exc_info=True)
            return False

        # The file data is safely written by this point, so a metadata failure
        # must not fail the backup. copystat raises on filesystems that cannot
        # represent the source's timestamps — notably exFAT, which stores no
        # date before 1980, while npm-installed files carry a 1970-01-01 mtime.
        # That combination raises [WinError 87] The parameter is incorrect.
        try:
            shutil.copystat(src, dst)
        except OSError as e:
            self.logger.debug("Metadata not copied for %s: %s", dst, e)

        self.logger.info("Copied %s → %s", src, dst)
        return True

    def upload_file(self, local_path, remote_path):
        return self._copy(local_path, remote_path)

    def download_file(self, remote_path, local_path):
        return self._copy(remote_path, local_path)

    def delete_file(self, remote_path):
        try:
            # Read-only files (git objects are mode 444) raise [WinError 5] on
            # remove, which would strand them on the destination forever — the
            # engine drops the manifest row only when the delete succeeds.
            self._clear_readonly(remote_path)
            os.remove(remote_path)
            self.logger.info("Deleted %s", remote_path)
            return True
        except FileNotFoundError:
            self.logger.warning("Delete skipped — file not found: %s", remote_path)
            return True
        except Exception as e:
            self.logger.error("Failed to delete %s: %s", remote_path, e, exc_info=True)
            return False

    def create_directory(self, remote_path):
        try:
            os.makedirs(remote_path, exist_ok=True)
            self.logger.info("Created directory %s", remote_path)
            return True
        except Exception as e:
            self.logger.error("Failed to create directory %s: %s", remote_path, e, exc_info=True)
            return False

    def path_exists(self, remote_path):
        return os.path.exists(remote_path)

    def list_files(self, remote_path):
        """List files (non-recursive) in remote_path. Yields (name, size, mtime)."""
        try:
            for entry in os.scandir(remote_path):
                if entry.is_file():
                    stat = entry.stat()
                    yield (entry.name, stat.st_size, stat.st_mtime)
        except Exception as e:
            self.logger.error("Error listing files in %s: %s", remote_path, e, exc_info=True)
            raise

class ShareConnector:
    def __init__(self, address, username, password):
        self.address = address
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)
        self._connected = False
        self._server_name = None

    def connect(self):
        """Establish SMB session and validate credentials."""
        try:
            self._server_name = self.address.lstrip('\\').split('\\')[0]
            smbclient.register_session(self._server_name, username=self.username, password=self.password)
            self._connected = True

            try:
                smbclient.listdir(self.address)
            except Exception as e:
                self.logger.warning("Connection registered but root listing failed: %s", e)

            self.logger.info("Connected to %s", self._server_name)
            return True
        except Exception as e:
            self.logger.error("Failed to connect to %s: %s", self.address, e, exc_info=True)
            return False

    def disconnect(self):
        if self._connected and self._server_name:
            try:
                smbclient.delete_session(self._server_name)
            except Exception as e:
                self.logger.warning("Error during disconnect from %s: %s", self._server_name, e)
            finally:
                self._connected = False
                self.logger.info("Disconnected from %s", self._server_name)

    def list_files(self, remote_path):
        """List files (non-recursive) in remote_path. Yields (name, size, mtime)."""
        try:
            full_path = self._build_path(remote_path)
            for entry in smbclient.scandir(full_path):
                if entry.is_file():
                    stat = entry.stat()
                    yield (entry.name, stat.st_size, stat.st_mtime)
        except Exception as e:
            self.logger.error("Error listing files in %s: %s", remote_path, e, exc_info=True)
            raise

    def upload_file(self, local_path, remote_path):
        try:
            full_remote = self._build_path(remote_path)
            remote_dir = os.path.dirname(full_remote)
            try:
                smbclient.makedirs(remote_dir, exist_ok=True)
            except Exception:
                pass

            with open(local_path, 'rb') as local_file:
                with smbclient.open_file(full_remote, mode='wb') as remote_file:
                    shutil.copyfileobj(local_file, remote_file)

            self.logger.info("Uploaded %s → %s", local_path, full_remote)
            return True
        except Exception as e:
            self.logger.error("Failed to upload %s to %s: %s", local_path, remote_path, e, exc_info=True)
            return False

    def download_file(self, remote_path, local_path):
        try:
            full_remote = self._build_path(remote_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            with smbclient.open_file(full_remote, mode='rb') as remote_file:
                with open(local_path, 'wb') as local_file:
                    shutil.copyfileobj(remote_file, local_file)

            self.logger.info("Downloaded %s → %s", full_remote, local_path)
            return True
        except Exception as e:
            self.logger.error("Failed to download %s to %s: %s", remote_path, local_path, e, exc_info=True)
            return False

    def delete_file(self, remote_path):
        try:
            smbclient.remove(self._build_path(remote_path))
            self.logger.info("Deleted %s", remote_path)
            return True
        except Exception as e:
            self.logger.error("Failed to delete %s: %s", remote_path, e, exc_info=True)
            return False

    def create_directory(self, remote_path):
        try:
            smbclient.makedirs(self._build_path(remote_path), exist_ok=True)
            self.logger.info("Created directory %s", remote_path)
            return True
        except Exception as e:
            self.logger.error("Failed to create directory %s: %s", remote_path, e, exc_info=True)
            return False

    def path_exists(self, remote_path):
        try:
            smbclient.stat(self._build_path(remote_path))
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            self.logger.error("Error checking path %s: %s", remote_path, e, exc_info=True)
            return False

    def _build_path(self, path):
        """Combine NAS address with a relative destination path into a full UNC path."""
        base = self.address.rstrip('\\')
        path = path.lstrip('\\')
        return base if not path else f"{base}\\{path}"
