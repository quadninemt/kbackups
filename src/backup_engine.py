import os
import logging
import time
import re
import zipfile
import tempfile
from datetime import datetime
from src.file_scanner import FileScanner
from src.manifest_manager import ManifestManager
from src.share_connector import ShareConnector, LocalConnector


class BackupEngine:
    # Resilient upload: retry files that fail (e.g. slow/failing OneDrive
    # hydration or transient network errors) after the first pass.
    MAX_UPLOAD_RETRIES = 2
    RETRY_BACKOFF_SECONDS = 3

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.file_scanner = FileScanner()
        self.manifest_manager = ManifestManager()
        self._stop_requested = False
        self._pause_requested = False
        # Paths of files that still failed after all retries in the last run.
        self.last_run_failures = []
        # Live counters for the dashboard indicators.
        self.stats = {'backed_up': 0, 'skipped': 0, 'deleted': 0, 'failed': 0}

    def request_stop(self):
        self._stop_requested = True

    def request_pause(self):
        self._pause_requested = True

    def resume(self):
        self._pause_requested = False

    def _check_pause_stop(self):
        """Returns True if stopped, blocking while paused."""
        if self._stop_requested:
            self.logger.info("Backup stopped by user.")
            return True
        while self._pause_requested:
            if self._stop_requested:
                self.logger.info("Backup stopped by user during pause.")
                return True
            time.sleep(0.5)
        return False

    def _get_source_folder_map(self, source_paths):
        """Build stable top-level destination folder names per source path."""
        source_folder_map = {}
        used_names = {}
        for source_path in source_paths:
            normalized = os.path.normpath(source_path)
            folder_name = os.path.basename(normalized)
            if not folder_name:
                drive, _ = os.path.splitdrive(normalized)
                folder_name = drive.replace(":", "") if drive else "source"
            count = used_names.get(folder_name, 0) + 1
            used_names[folder_name] = count
            if count > 1:
                folder_name = f"{folder_name}_{count}"
            source_folder_map[source_path] = folder_name
        return source_folder_map

    @staticmethod
    def _is_local_destination(path):
        """Return True if path is a local filesystem path (not a UNC/SMB path)."""
        if not path:
            return False
        s = path.strip()
        if s.startswith('\\\\') or s.startswith('//'):
            return False
        return len(s) >= 2 and s[1] == ':'

    def _create_connector(self, destination_path, nas_config):
        """Return the appropriate connector for the destination path."""
        if self._is_local_destination(destination_path):
            self.logger.info("Destination '%s' is a local path — using LocalConnector.", destination_path)
            return LocalConnector()
        nas_address = nas_config.get("address")
        nas_user = nas_config.get("username")
        nas_pass = nas_config.get("password")
        if not nas_address or not nas_user:
            return None
        return ShareConnector(nas_address, nas_user, nas_pass)

    def _sanitize_job_name(self, job_name):
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", (job_name or "").strip())
        return safe.strip("_") or "job"

    def _create_snapshot_zip(self, job_name):
        config_path = os.path.abspath(getattr(self.config_manager, "config_path", ""))
        manifest_path = os.path.abspath(self.manifest_manager.db_path)

        for source_path in (config_path, manifest_path):
            if not source_path or not os.path.exists(source_path):
                raise FileNotFoundError(f"Snapshot source file missing: {source_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_job_name = self._sanitize_job_name(job_name)
        snapshot_name = f"_k_backups_snapshot_{safe_job_name}_{timestamp}.zip"
        snapshot_path = os.path.join(tempfile.gettempdir(), snapshot_name)

        with zipfile.ZipFile(snapshot_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(config_path, arcname="config/settings.json")
            zf.write(manifest_path, arcname="config/manifest.db")

        return snapshot_path, snapshot_name

    def _cleanup_old_job_snapshots(self, connector, job_name, destination_folder, keep_snapshot_name):
        safe_job_name = self._sanitize_job_name(job_name)
        snapshot_prefix = f"_k_backups_snapshot_{safe_job_name}_"
        try:
            remote_files = list(connector.list_files(destination_folder))
        except Exception as e:
            self.logger.error("Failed to list destination for snapshot cleanup (job '%s'): %s", job_name, e, exc_info=True)
            return False

        for name, _, _ in remote_files:
            if name.startswith(snapshot_prefix) and name.endswith(".zip") and name != keep_snapshot_name:
                remote_path = os.path.join(destination_folder, name)
                if not connector.delete_file(remote_path):
                    self.logger.error("Failed to delete old snapshot for job '%s': %s", job_name, remote_path)
                    return False
                self.logger.info("Deleted old snapshot for job '%s': %s", job_name, remote_path)
        return True

    def _upload_job_snapshot(self, connector, job_name, destination_folder, progress_callback=None):
        snapshot_path = None
        try:
            snapshot_path, snapshot_name = self._create_snapshot_zip(job_name)
            remote_snapshot_path = os.path.join(destination_folder, snapshot_name)

            if progress_callback:
                progress_callback(0, 0, f"Uploading job snapshot: {snapshot_name}...")

            if not connector.upload_file(snapshot_path, remote_snapshot_path):
                self.logger.error("Failed to upload snapshot for job '%s' to '%s'.", job_name, remote_snapshot_path)
                return False

            if progress_callback:
                progress_callback(0, 0, "Removing older snapshots...")

            if not self._cleanup_old_job_snapshots(connector, job_name, destination_folder, snapshot_name):
                self.logger.error("Failed to enforce snapshot retention for job '%s'.", job_name)
                return False

            self.logger.info("Snapshot uploaded for job '%s': %s", job_name, remote_snapshot_path)
            return True
        except Exception as e:
            self.logger.error("Failed to create/upload snapshot for job '%s': %s", job_name, e, exc_info=True)
            return False
        finally:
            if snapshot_path and os.path.exists(snapshot_path):
                try:
                    os.remove(snapshot_path)
                except OSError:
                    self.logger.warning("Failed to remove temporary snapshot file: %s", snapshot_path, exc_info=True)

    def run_job(self, job_name, progress_callback=None):
        """Run a backup job by name. progress_callback(current, total, message)."""
        self._stop_requested = False
        self._pause_requested = False
        self.last_run_failures = []
        self.stats = {'backed_up': 0, 'skipped': 0, 'deleted': 0, 'failed': 0}
        self.logger.info("Starting backup job '%s'.", job_name)

        jobs = self.config_manager.get_jobs()
        job_config = next((j for j in jobs if j.get("name") == job_name), None)
        if not job_config:
            self.logger.error("Job '%s' not found.", job_name)
            return False

        source_paths = job_config.get("source_paths", [])
        excludes = job_config.get("exclude_patterns", [])
        destination_folder = job_config.get("destination_path", "")
        self.logger.info("Job '%s': %d source(s), destination='%s', %d exclude(s).",
                         job_name, len(source_paths), destination_folder, len(excludes))

        nas_config = self.config_manager.get_nas_settings()
        connector = self._create_connector(destination_folder, nas_config)
        if connector is None:
            self.logger.error("NAS configuration missing and destination is not a local path.")
            if progress_callback:
                progress_callback(0, 0, "Error: NAS address and username are required for network destinations.")
            return False

        if not connector.connect():
            if progress_callback:
                progress_callback(0, 0, "Failed to connect to destination.")
            return False

        try:
            if not self._validate_and_prepare_destination(connector, destination_folder, progress_callback):
                return False

            if self._check_pause_stop():
                return False

            if progress_callback:
                progress_callback(0, 0, "Scanning local files...")

            valid_sources = []
            for src in source_paths:
                if os.path.exists(src):
                    valid_sources.append(src)
                else:
                    msg = f"Warning: Source path not found: {src}"
                    self.logger.warning(msg)
                    if progress_callback:
                        progress_callback(0, 0, msg)

            if not valid_sources:
                msg = "Error: No valid source paths found."
                self.logger.error(msg)
                if progress_callback:
                    progress_callback(0, 0, msg)
                return False

            source_folder_map = self._get_source_folder_map(valid_sources)
            local_files = []
            scanned_total = 0
            for src in valid_sources:
                folder_label = os.path.basename(os.path.normpath(src)) or src
                if progress_callback:
                    progress_callback(0, 0, f"Scanning: {src}")
                self.logger.info("Scanning source '%s'...", src)

                def _scan_progress(count, _src=src, _label=folder_label):
                    if progress_callback:
                        progress_callback(0, 0, f"Scanning {_label}... {scanned_total + count:,} files found")

                source_files = self.file_scanner.scan([src], excludes, progress_callback=_scan_progress)
                scanned_total += len(source_files)

                folder = source_folder_map[src]
                for file_meta in source_files:
                    meta = file_meta.copy()
                    meta['rel_path'] = os.path.join(folder, file_meta['rel_path'])
                    local_files.append(meta)

                if progress_callback:
                    progress_callback(0, 0, f"Scanned {len(source_files):,} files in {folder_label}")
                self.logger.info("Scanned %d files in '%s'.", len(source_files), src)

            local_files_map = {f['path']: f for f in local_files}
            if progress_callback:
                progress_callback(0, 0, f"Scan complete: {len(local_files_map):,} files total. Comparing with last backup...")

            if self._check_pause_stop():
                return False

            manifest_files = self.manifest_manager.get_job_files(job_name)

            to_upload = []
            to_delete = []

            for path, meta in local_files_map.items():
                if self._check_pause_stop():
                    return False
                manifest_meta = manifest_files.get(path)
                if not manifest_meta:
                    to_upload.append(meta)
                else:
                    time_diff = abs(meta['mtime'] - manifest_meta['mtime'])
                    if (meta['size'] != manifest_meta['size']
                            or time_diff > 2.0
                            or meta['rel_path'] != manifest_meta.get('rel_path')):
                        to_upload.append(meta)

            for path, meta in manifest_files.items():
                if self._check_pause_stop():
                    return False
                if path not in local_files_map:
                    to_delete.append((path, meta))

            total_ops = len(to_upload) + len(to_delete)
            # Files present locally and unchanged vs the manifest (already up to date).
            self.stats['skipped'] = max(0, len(local_files_map) - len(to_upload))
            self.logger.info("Job '%s': %d upload(s), %d delete(s), %d skipped (up to date).",
                             job_name, len(to_upload), len(to_delete), self.stats['skipped'])
            if progress_callback:
                progress_callback(0, total_ops,
                                  f"Scan result: {len(to_upload):,} to back up, "
                                  f"{self.stats['skipped']:,} up to date, {len(to_delete):,} to delete.")

            processed = 0
            manifest_deletes = []
            manifest_updates = []

            # Process deletes
            for path, item in to_delete:
                if self._check_pause_stop():
                    return False
                rel_path = item['rel_path']
                remote_rel_path = os.path.join(destination_folder, rel_path)
                if progress_callback:
                    progress_callback(processed, total_ops, f"Deleting {rel_path}...")
                if connector.delete_file(remote_rel_path):
                    manifest_deletes.append(path)
                    self.stats['deleted'] += 1
                processed += 1

            # Process uploads — first pass; collect failures for retry
            failed = []
            for meta in to_upload:
                if self._check_pause_stop():
                    return False
                rel_path = meta['rel_path']
                if progress_callback:
                    progress_callback(processed, total_ops, f"Uploading {rel_path}...")

                ok, payload = self._upload_one(connector, meta, destination_folder)
                if ok:
                    if payload:
                        manifest_updates.append(payload)
                    self.stats['backed_up'] += 1
                else:
                    meta['_error'] = payload
                    failed.append(meta)
                    self.stats['failed'] = len(failed)
                    self.logger.warning("Upload failed (%s): %s", payload, meta['path'])
                    if progress_callback:
                        progress_callback(processed, total_ops, f"Failed ({payload}): {rel_path} — will retry")
                processed += 1

            # Retry passes for failed files (handles flaky OneDrive/network)
            for attempt in range(1, self.MAX_UPLOAD_RETRIES + 1):
                if not failed:
                    break
                if self._check_pause_stop():
                    return False
                self.logger.info("Retry pass %d/%d for %d failed file(s) (job '%s').",
                                 attempt, self.MAX_UPLOAD_RETRIES, len(failed), job_name)
                if progress_callback:
                    progress_callback(processed, total_ops,
                                      f"Retry {attempt}/{self.MAX_UPLOAD_RETRIES}: {len(failed)} file(s) failed, retrying...")
                time.sleep(self.RETRY_BACKOFF_SECONDS)

                still_failed = []
                for meta in failed:
                    if self._check_pause_stop():
                        return False
                    rel_path = meta['rel_path']
                    if progress_callback:
                        progress_callback(processed, total_ops, f"Retrying ({attempt}) {rel_path}...")
                    ok, payload = self._upload_one(connector, meta, destination_folder)
                    if ok:
                        if payload:
                            manifest_updates.append(payload)
                        self.stats['backed_up'] += 1
                        self.logger.info("Retry succeeded: %s", meta['path'])
                    else:
                        meta['_error'] = payload
                        still_failed.append(meta)
                failed = still_failed
                self.stats['failed'] = len(failed)

            # Record persistent failures with their last error (not added to the
            # manifest, so the next run retries them).
            self.last_run_failures = [
                {'path': m['path'], 'error': m.get('_error', 'unknown error')}
                for m in failed
            ]
            self.stats['failed'] = len(failed)
            if failed:
                self.logger.warning(
                    "=== Job '%s': %d file(s) FAILED after %d retries ===",
                    job_name, len(failed), self.MAX_UPLOAD_RETRIES)
                for m in failed:
                    self.logger.warning("  FAILED: %s", m['path'])

            # Flush manifest changes in two batch transactions
            self.manifest_manager.batch_remove_files(job_name, manifest_deletes)
            self.manifest_manager.batch_update_files(job_name, manifest_updates)

            if progress_callback:
                progress_callback(processed, total_ops, "Creating and uploading job snapshot...")

            if not self._upload_job_snapshot(connector, job_name, destination_folder, progress_callback):
                if progress_callback:
                    progress_callback(processed, total_ops, "Backup failed: could not upload job snapshot.")
                return False

            failure_count = len(self.last_run_failures)
            if failure_count:
                final_msg = f"Backup completed with {failure_count} failed file(s) — see log."
            else:
                final_msg = "Backup completed successfully."
            if progress_callback:
                progress_callback(total_ops, total_ops, final_msg)

            self.logger.info("Backup job '%s' completed. %d uploaded, %d failed after retries.",
                             job_name, len(manifest_updates), failure_count)
            return True

        except Exception as e:
            self.logger.error("Backup failed: %s", e, exc_info=True)
            if progress_callback:
                progress_callback(0, 0, f"Error: {e}")
            return False
        finally:
            connector.disconnect()

    def _upload_one(self, connector, meta, destination_folder):
        """
        Attempt to hydrate (if needed) and upload a single file.
        Returns (success: bool, payload):
          - success True, payload = manifest tuple (path, rel_path, size, mtime) or None
          - success False, payload = short reason string
        """
        full_path = meta['path']
        rel_path = meta['rel_path']

        if meta.get('is_placeholder'):
            if not self.file_scanner.hydrate_file(full_path):
                return (False, "hydration failed")

        remote_rel_path = os.path.join(destination_folder, rel_path)
        if connector.upload_file(full_path, remote_rel_path):
            try:
                stat = os.stat(full_path)
                return (True, (full_path, rel_path, stat.st_size, stat.st_mtime))
            except OSError:
                self.logger.warning("Stat refresh failed after upload: %s", full_path, exc_info=True)
                return (True, None)
        return (False, "upload failed")

    def _validate_and_prepare_destination(self, connector, destination_folder, progress_callback):
        try:
            if not connector.path_exists(destination_folder):
                if progress_callback:
                    progress_callback(0, 0, f"Creating remote directory: {destination_folder}")
                return connector.create_directory(destination_folder)
            return True
        except Exception as e:
            msg = f"Failed to access/create destination '{destination_folder}': {e}"
            self.logger.error(msg, exc_info=True)
            if progress_callback:
                progress_callback(0, 0, msg)
            return False

    def restore_job(self, job_name, restore_dest, progress_callback=None):
        """Restore all files for a job from NAS to a local folder."""
        self.logger.info("Starting restore job '%s' to '%s'.", job_name, restore_dest)

        jobs = self.config_manager.get_jobs()
        job_config = next((j for j in jobs if j.get("name") == job_name), None)
        if not job_config:
            self.logger.error("Job '%s' not found.", job_name)
            return False

        nas_config = self.config_manager.get_nas_settings()
        job_folder = job_config.get("destination_path", "")
        connector = self._create_connector(job_folder, nas_config)
        if connector is None:
            self.logger.error("NAS configuration missing for restore job '%s'.", job_name)
            return False

        if not connector.connect():
            if progress_callback:
                progress_callback(0, 0, "Failed to connect to destination.")
            return False

        try:
            manifest_files = self.manifest_manager.get_job_files(job_name)
            total_files = len(manifest_files)
            processed = 0

            if progress_callback:
                progress_callback(0, total_files, "Starting restore...")

            for original_path, meta in manifest_files.items():
                rel_path = meta['rel_path']
                remote_rel_path = os.path.join(job_folder, rel_path)
                local_dest_path = os.path.join(restore_dest, rel_path)

                if progress_callback:
                    progress_callback(processed, total_files, f"Restoring {rel_path}...")

                connector.download_file(remote_rel_path, local_dest_path)
                processed += 1

            if progress_callback:
                progress_callback(total_files, total_files, "Restore completed.")

            self.logger.info("Restore job '%s' completed successfully.", job_name)
            return True

        except Exception as e:
            self.logger.error("Restore failed: %s", e, exc_info=True)
            if progress_callback:
                progress_callback(0, 0, f"Error: {e}")
            return False
        finally:
            connector.disconnect()
