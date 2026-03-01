import json
import os
import sys
import logging
import shutil

class ConfigManager:
    DEFAULT_CONFIG = {
        "nas": {
            "address": "",
            "username": "",
            "password": ""
        },
        "jobs": []
    }

    def __init__(self, config_path=None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self.DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger(__name__)
        self.load_config()

    def _get_default_config_path(self):
        # Canonical location for both dev and packaged app:
        # <app-root>/config/settings.json
        app_root = self._get_app_root()
        return os.path.abspath(os.path.join(app_root, "config", "settings.json"))

    def _get_app_root(self):
        if getattr(sys, 'frozen', False):
            # Running as compiled executable (PyInstaller)
            return os.path.dirname(sys.executable)

        # Running as python script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(current_dir)

    def _get_legacy_config_candidates(self):
        app_root = self._get_app_root()
        candidates = [
            os.path.join(app_root, "settings.json"),
        ]

        if getattr(sys, 'frozen', False):
            # Older builds may have looked one level up.
            candidates.append(os.path.join(os.path.dirname(app_root), "settings.json"))

        return [os.path.abspath(path) for path in candidates]

    def _migrate_legacy_config_if_needed(self):
        if os.path.exists(self.config_path):
            return

        for legacy_path in self._get_legacy_config_candidates():
            if os.path.exists(legacy_path):
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                shutil.copy2(legacy_path, self.config_path)
                self.logger.info(
                    f"Migrated legacy config from {legacy_path} to {self.config_path}."
                )
                return

    def load_config(self):
        """Load configuration from the JSON file."""
        self._migrate_legacy_config_if_needed()

        if not os.path.exists(self.config_path):
            self.logger.info(f"Config file not found at {self.config_path}. Creating default.")
            self.save_config()
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.logger.info("Configuration loaded successfully.")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON config: {e}. Using defaults.")
            try:
                invalid_backup = f"{self.config_path}.invalid"
                shutil.copy2(self.config_path, invalid_backup)
                self.logger.info(f"Invalid config backed up to {invalid_backup}.")
            except Exception as backup_error:
                self.logger.error(f"Failed to backup invalid config: {backup_error}", exc_info=True)

            self.config = self.DEFAULT_CONFIG.copy()
            self.save_config()
        except Exception as e:
            self.logger.error(f"Error loading config: {e}", exc_info=True)

    def save_config(self):
        """Save current configuration to the JSON file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            self.logger.info("Configuration saved successfully.")
        except Exception as e:
            self.logger.error(f"Error saving config: {e}", exc_info=True)

    def get_nas_settings(self):
        return self.config.get("nas", {})

    def set_nas_settings(self, address, username, password):
        self.config["nas"] = {
            "address": address,
            "username": username,
            "password": password
        }
        self.save_config()

    def get_jobs(self):
        return self.config.get("jobs", [])

    def add_job(self, job_data):
        self.config.setdefault("jobs", []).append(job_data)
        self.save_config()

    def update_job(self, job_index, job_data):
        if 0 <= job_index < len(self.config.get("jobs", [])):
            self.config["jobs"][job_index] = job_data
            self.save_config()
            return True
        return False

    def delete_job(self, job_index):
        if 0 <= job_index < len(self.config.get("jobs", [])):
            self.config["jobs"].pop(job_index)
            self.save_config()
            return True
        return False
