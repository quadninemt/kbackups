import os
import logging
from src.file_scanner import FileScanner
from src.manifest_manager import ManifestManager
from src.share_connector import ShareConnector

class BackupEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.file_scanner = FileScanner()
        self.manifest_manager = ManifestManager()

    def run_job(self, job_name, progress_callback=None):
        """
        Run a backup job by name.
        progress_callback: function(current_step, total_steps, message)
        """
        # 1. Get job configuration
        jobs = self.config_manager.get_jobs()
        job_config = next((j for j in jobs if j.get("name") == job_name), None)
        
        if not job_config:
            self.logger.error(f"Job '{job_name}' not found.")
            return False

        source_paths = job_config.get("source_paths", [])
        excludes = job_config.get("exclude_patterns", [])
        destination_folder = job_config.get("destination_path", "") # e.g., "MyBackup"
        
        nas_config = self.config_manager.get_nas_settings()
        nas_address = nas_config.get("address")
        nas_user = nas_config.get("username")
        nas_pass = nas_config.get("password")

        if not nas_address or not nas_user:
            self.logger.error("NAS configuration missing.")
            return False

        # 2. Connect to NAS
        connector = ShareConnector(nas_address, nas_user, nas_pass)
        if not connector.connect():
            if progress_callback:
                progress_callback(0, 0, "Failed to connect to NAS")
            return False

        try:
            # 3. Scan local files
            if progress_callback:
                progress_callback(0, 0, "Scanning local files...")
            
            local_files = self.file_scanner.scan(source_paths, excludes)
            # Map path -> metadata for O(1) lookup
            local_files_map = {f['path']: f for f in local_files}
            
            # 4. Get manifest
            manifest_files = self.manifest_manager.get_job_files(job_name)
            
            # 5. Diff & Identify operations
            to_upload = []  # List of local file metadata dicts
            to_delete = []  # List of (path, metadata_dict) tuples
            
            # Detect new or changed files
            for path, meta in local_files_map.items():
                manifest_meta = manifest_files.get(path)
                
                is_changed = False
                if not manifest_meta:
                    is_changed = True # New file
                else:
                    # Compare size and mtime
                    # Use a small tolerance for mtime (e.g. 2 seconds for FAT/SMB differences)
                    time_diff = abs(meta['mtime'] - manifest_meta['mtime'])
                    if meta['size'] != manifest_meta['size'] or time_diff > 2.0:
                        is_changed = True
                
                if is_changed:
                    to_upload.append(meta)

            # Detect deleted files (present in manifest but not locally)
            for path, meta in manifest_files.items():
                if path not in local_files_map:
                    to_delete.append((path, meta))

            total_ops = len(to_upload) + len(to_delete)
            if progress_callback:
                progress_callback(0, total_ops, f"Found {len(to_upload)} files to upload, {len(to_delete)} to delete.")
            
            processed = 0
            
            # 6. Process Delete
            for path, item in to_delete:
                rel_path = item['rel_path']
                # Construct remote path
                # Note: destination_folder might be empty or a subfolder on the share
                # share_connector joins addresses.
                # If destination_folder is "MyBackup", and rel_path is "Photos/img.jpg" -> "MyBackup/Photos/img.jpg"
                remote_rel_path = os.path.join(destination_folder, rel_path).replace("\\", "/") # Ensure forward slashes for smbclient sometimes? No backslashes are fine on Windows, but smbclient handles both usually. Let's stick to os.path.join.
                
                if progress_callback:
                    progress_callback(processed, total_ops, f"Deleting {rel_path}...")
                
                if connector.delete_file(remote_rel_path):
                   self.manifest_manager.remove_file_state(job_name, path)
                
                processed += 1
            
            # 7. Process Upload
            for meta in to_upload:
                full_path = meta['path']
                rel_path = meta['rel_path']
                
                if progress_callback:
                    progress_callback(processed, total_ops, f"Uploading {rel_path}...")
                
                # Hydrate if needed
                if meta.get('is_placeholder'):
                    if not self.file_scanner.hydrate_file(full_path):
                         self.logger.warning(f"Skipping upload for {full_path}: Hydration failed.")
                         processed += 1
                         continue

                remote_rel_path = os.path.join(destination_folder, rel_path)
                
                # We need to ensure directory exists before upload? 
                # ShareConnector.upload_file handles directory creation.
                if connector.upload_file(full_path, remote_rel_path):
                    # Update manifest
                    # We might want to re-stat the file to get exact size/mtime after upload/hydration
                    try:
                        uploaded_stat = os.stat(full_path)
                        self.manifest_manager.update_file_state(
                            job_name, 
                            full_path, 
                            rel_path, 
                            uploaded_stat.st_size, 
                            uploaded_stat.st_mtime
                        )
                    except OSError:
                         pass
                
                processed += 1
            
            if progress_callback:
                progress_callback(total_ops, total_ops, "Backup completed successfully.")
            
            return True

        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            if progress_callback:
                progress_callback(0, 0, f"Error: {str(e)}")
            return False
            
        finally:
            connector.disconnect()

    def restore_job(self, job_name, restore_dest, progress_callback=None):
        """Restore all files for a job to a local folder."""
        # 1. Get job configuration
        jobs = self.config_manager.get_jobs()
        job_config = next((j for j in jobs if j.get("name") == job_name), None)
        
        if not job_config:
            self.logger.error(f"Job '{job_name}' not found.")
            return False

        nas_config = self.config_manager.get_nas_settings()
        nas_address = nas_config.get("address")
        nas_user = nas_config.get("username")
        nas_pass = nas_config.get("password")
        
        job_folder = job_config.get("destination_path", "")

        if not nas_address or not nas_user:
            return False

        connector = ShareConnector(nas_address, nas_user, nas_pass)
        if not connector.connect():
            if progress_callback: progress_callback(0, 0, "Failed to connect to NAS")
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
            return True
            
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            if progress_callback: progress_callback(0, 0, f"Error: {e}")
            return False
        finally:
            connector.disconnect()
