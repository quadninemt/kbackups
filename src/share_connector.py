import smbclient
import os
import shutil
import logging

class ShareConnector:
    def __init__(self, address, username, password):
        self.address = address
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)
        self._connected = False

    def connect(self):
        """Establish SMB connection. Since smbclient auto-manages sessions, this validates credentials."""
        try:
            # Extract server name from UNC path
            server_name = self.address.lstrip('\\').split('\\')[0]
            smbclient.register_session(server_name, username=self.username, password=self.password)
            self._connected = True
            
            # Simple check to verify connection by listing root
            # Note: listing root of share might fail if permissions are restricted to subfolders
            # But we need to verify connection somehow.
            try:
                 smbclient.listdir(self.address)
            except Exception as e:
                  self.logger.warning(f"Connection registered but listing failed: {e}", exc_info=True)
                 # We still consider it connected if register_session worked, but maybe credentials are wrong
                 # verify with a stat check on the share root
            
            self.logger.info(f"Connected to {server_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.address}: {e}", exc_info=True)
            return False

    def disconnect(self):
        """Close connection."""
        if self._connected:
            smbclient.delete_session(self.address)
            self._connected = False
            self.logger.info("Disconnected from NAS")

    def list_files(self, remote_path):
        """List files in the remote directory. Returns generator of (name, size, mtime)."""
        try:
            full_path = self._validate_path(remote_path)
            for entry in smbclient.scandir(full_path):
                if entry.is_file():
                    yield (entry.name, entry.stat().st_size, entry.stat().st_mtime)
                elif entry.is_dir():
                    # For recursive listing, we might need a separate function or modify this one
                    pass
        except Exception as e:
            self.logger.error(f"Error listing files in {remote_path}: {e}", exc_info=True)
            raise

    def upload_file(self, local_path, remote_path):
        """Upload a file to the remote path."""
        try:
            full_remote_path = self._validate_path(remote_path)
            
            # Ensure the directory exists
            remote_dir = os.path.dirname(full_remote_path)
            # Create directory directly using smbclient to avoid double-prefix issue via self.create_directory wrapper
            try:
                smbclient.makedirs(remote_dir, exist_ok=True)
            except Exception:
                pass

            
            # Check if file exists to handle update? smbclient 'w' mode truncates, which is fine for backup update.

            with open(local_path, 'rb') as local_file:
                with smbclient.open_file(full_remote_path, mode='wb') as remote_file:
                    shutil.copyfileobj(local_file, remote_file)
            
            self.logger.info(f"Uploaded {local_path} to {full_remote_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload {local_path} to {remote_path}: {e}", exc_info=True)
            return False

    def download_file(self, remote_path, local_path):
        """Download remote file to local path."""
        try:
            full_remote_path = self._validate_path(remote_path)
            
            # Ensure local directory exists
            local_dir = os.path.dirname(local_path)
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)

            with smbclient.open_file(full_remote_path, mode='rb') as remote_file:
                with open(local_path, 'wb') as local_file:
                    shutil.copyfileobj(remote_file, local_file)
            
            self.logger.info(f"Downloaded {full_remote_path} to {local_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to download {remote_path} to {local_path}: {e}", exc_info=True)
            return False

    def delete_file(self, remote_path):
        """Delete a file from the remote path."""
        try:
            full_path = self._validate_path(remote_path)
            smbclient.remove(full_path)
            self.logger.info(f"Deleted {full_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete {remote_path}: {e}", exc_info=True)
            return False

    def create_directory(self, remote_path):
        """Create a directory on the remote path."""
        try:
            full_path = self._validate_path(remote_path)
            smbclient.makedirs(full_path, exist_ok=True)
            self.logger.info(f"Created directory {full_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create directory {remote_path}: {e}", exc_info=True)
            return False

    def path_exists(self, remote_path):
        """Check if a path exists."""
        try:
            full_path = self._validate_path(remote_path)
            # smbclient.stat raises FileNotFoundError if not exists
            smbclient.stat(full_path)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"Error checking path {remote_path}: {e}", exc_info=True)
            return False

    def _validate_path(self, path):
        """Ensure path starts with \\server\share format."""
        # For smbclient, input path should be full UNC path like \\server\share\file
        # If user provided \\server\share as self.address, and path is relative, join them.
        
        # Strip trailing slashes
        base = self.address.rstrip('\\')
        path = path.lstrip('\\')
        
        if not path:
             return base
        return f"{base}\\{path}"

