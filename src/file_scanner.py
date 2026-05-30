import os
import glob
import fnmatch
import logging

class FileScanner:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # Emit a scan-progress update roughly every this many files found.
    SCAN_PROGRESS_INTERVAL = 1000

    def scan(self, source_paths, excludes=None, progress_callback=None):
        """
        Scan directories for files, respecting exclude patterns.
        source_paths: List of directory paths to scan. (Make sure absolute paths are used)
        excludes: List of glob patterns to exclude (e.g., "*.tmp", "temp/").
        progress_callback: optional fn(files_found_so_far) called periodically while scanning.
        Returns a list of dicts: {'path': full_path, 'rel_path': relative_path, 'size': size, 'mtime': mtime}
        """
        excludes = excludes or []
        file_list = []

        for source_path in source_paths:
            if not os.path.exists(source_path):
                self.logger.warning(f"Source path not found: {source_path}")
                continue

            source_path = os.path.abspath(source_path)

            for root, dirs, files in os.walk(source_path):
                # Exclude directories
                # Modify dirs in-place to skip traversing excluded directories
                # We need to match relative path or name against exclude patterns
                dirs[:] = [d for d in dirs if not self._is_excluded(os.path.join(root, d), source_path, excludes)]

                for file in files:
                    full_path = os.path.join(root, file)
                    if self._is_excluded(full_path, source_path, excludes):
                        continue

                    try:
                        stat = os.stat(full_path)
                        rel_path = os.path.relpath(full_path, source_path)

                        is_placeholder = self._is_onedrive_placeholder(full_path)

                        file_list.append({
                            'path': full_path,     # Absolute path
                            'rel_path': rel_path,  # Relative to source root (for mirroring structure)
                            'size': stat.st_size,
                            'mtime': stat.st_mtime,
                            'is_placeholder': is_placeholder
                        })

                        if progress_callback and len(file_list) % self.SCAN_PROGRESS_INTERVAL == 0:
                            progress_callback(len(file_list))
                    except OSError as e:
                        self.logger.error(f"Error accessing file {full_path}: {e}", exc_info=True)

        self.logger.info(f"Scanned {len(file_list)} files.")
        return file_list

    def hydrate_file(self, file_path):
        """
        Trigger Windows hydration by reading first byte of file.
        This forces download of OneDrive placeholder.
        """
        try:
            if not self._is_onedrive_placeholder(file_path):
                return True
                
            self.logger.info(f"Hydrating file: {file_path}")
            # Identify file size first to ensure we don't read huge file fully if not needed
            # Reading 1 byte is enough to trigger hydration
            with open(file_path, 'rb') as f:
                f.read(1)
            return True
        except Exception as e:
            self.logger.error(f"Failed to hydrate {file_path}: {e}", exc_info=True)
            return False

    def _is_excluded(self, path, base_path, excludes):
        """Check if path matches any exclude pattern."""
        # Check against base name
        if any(fnmatch.fnmatch(os.path.basename(path), pattern) for pattern in excludes):
            return True
        
        # Check against relative path
        rel_path = os.path.relpath(path, base_path)
        if any(fnmatch.fnmatch(rel_path, pattern) for pattern in excludes):
            return True
            
        return False

    def _is_onedrive_placeholder(self, file_path):
        """
        Check if file is a OneDrive placeholder.
        Uses FILE_ATTRIBUTE_REPARSE_POINT (0x400) + checking reparse tag if possible,
        or file attributes generally associated with offline files.
        FILE_ATTRIBUTE_OFFLINE = 0x1000
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        """
        try:
            attrs = os.stat(file_path).st_file_attributes
            is_offline = bool(attrs & 0x1000)
            is_reparse = bool(attrs & 0x400)
            # If it's offline and a reparse point, likely a placeholder
            return is_offline and is_reparse
        except AttributeError:
            # st_file_attributes only on Windows
            return False
        except Exception:
            return False
