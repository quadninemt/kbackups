import os
import glob
import fnmatch
import logging

class FileScanner:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # Emit a scan-progress update roughly every this many files found.
    SCAN_PROGRESS_INTERVAL = 1000

    # Windows reserved device names. A file with one of these base names (any
    # extension) resolves to a device path like \\.\nul, which breaks
    # os.path.relpath and can't be backed up. Skip them defensively.
    _WINDOWS_RESERVED = {
        'con', 'prn', 'aux', 'nul',
        *(f'com{i}' for i in range(1, 10)),
        *(f'lpt{i}' for i in range(1, 10)),
    }

    # Chromium/Electron cache directories (VS Code, Claude Desktop, Slack, etc.).
    # These are regenerated on next launch, are held open while the app runs — so
    # they fail to copy with "Permission denied" — and are worthless in a restore.
    # Excluded from every job. Names here are unambiguous product artefacts, not
    # words a user would plausibly name their own folder.
    DEFAULT_EXCLUDES = (
        'Cache_Data',
        'CachedConfigurations',
        'CachedData',
        'CachedExtensionVSIXs',
        'CachedProfilesData',
        'Code Cache',
        'Crashpad',
        'DawnGraphiteCache',
        'DawnWebGPUCache',
        'GPUCache',
        'ShaderCache',
        'blob_storage',
    )

    @classmethod
    def _is_reserved_name(cls, name):
        # Strip extension: 'nul.txt' is still the reserved device 'nul' on Windows.
        stem = name.split('.', 1)[0].strip().lower()
        return stem in cls._WINDOWS_RESERVED

    def scan(self, source_paths, excludes=None, progress_callback=None):
        """
        Scan sources for files, respecting exclude patterns.
        source_paths: List of paths to scan. Each may be a directory (walked
                      recursively) or a single file. (Use absolute paths.)
        excludes: List of glob patterns to exclude (e.g., "*.tmp", "temp/").
                  Applied on top of DEFAULT_EXCLUDES, which always apply.
        progress_callback: optional fn(files_found_so_far) called periodically while scanning.
        Returns a list of dicts: {'path': full_path, 'rel_path': relative_path, 'size': size, 'mtime': mtime}
        """
        excludes = list(self.DEFAULT_EXCLUDES) + list(excludes or [])
        file_list = []

        for source_path in source_paths:
            if not os.path.exists(source_path):
                self.logger.warning(f"Source path not found: {source_path}")
                continue

            source_path = os.path.abspath(source_path)
            found_before = len(file_list)

            if os.path.isfile(source_path):
                # A single file as a source. Its rel_path is just the file name,
                # so it mirrors to the destination root rather than into a
                # folder named after itself.
                name = os.path.basename(source_path)
                if self._is_reserved_name(name):
                    self.logger.warning(f"Skipping Windows reserved name: {source_path}")
                elif not any(fnmatch.fnmatch(name, pattern) for pattern in excludes):
                    self._collect_file(file_list, source_path, name, progress_callback)
            else:
                for root, dirs, files in os.walk(source_path):
                    # Exclude directories
                    # Modify dirs in-place to skip traversing excluded directories
                    # We need to match relative path or name against exclude patterns
                    dirs[:] = [d for d in dirs if not self._is_excluded(os.path.join(root, d), source_path, excludes)]

                    for file in files:
                        full_path = os.path.join(root, file)
                        if self._is_reserved_name(file):
                            self.logger.warning(f"Skipping Windows reserved name: {full_path}")
                            continue
                        if self._is_excluded(full_path, source_path, excludes):
                            continue

                        try:
                            rel_path = os.path.relpath(full_path, source_path)
                        except ValueError as e:
                            self.logger.error(f"Error accessing file {full_path}: {e}", exc_info=True)
                            continue
                        self._collect_file(file_list, full_path, rel_path, progress_callback)

            # A source that contributes nothing is almost always a mistake (bad
            # path, or an exclude pattern that swallowed everything). Backing up
            # nothing must never be silent.
            if len(file_list) == found_before:
                self.logger.warning(
                    "Source '%s' contributed 0 files — check the path and this job's exclude patterns.",
                    source_path)

        self.logger.info(f"Scanned {len(file_list)} files.")
        return file_list

    def _collect_file(self, file_list, full_path, rel_path, progress_callback):
        """Stat a file and append its metadata entry. Errors are logged and skipped."""
        try:
            stat = os.stat(full_path)

            file_list.append({
                'path': full_path,     # Absolute path
                'rel_path': rel_path,  # Relative to source root (for mirroring structure)
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'is_placeholder': self._is_onedrive_placeholder(full_path)
            })

            if progress_callback and len(file_list) % self.SCAN_PROGRESS_INTERVAL == 0:
                progress_callback(len(file_list))
        except (OSError, ValueError) as e:
            self.logger.error(f"Error accessing file {full_path}: {e}", exc_info=True)

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
        
        # Check against relative path. relpath can raise ValueError when the
        # path resolves to a different mount/device (e.g. a Windows reserved
        # name); fall back to the basename check only and let the caller's
        # guarded relpath surface the problem.
        try:
            rel_path = os.path.relpath(path, base_path)
        except ValueError:
            return False
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
