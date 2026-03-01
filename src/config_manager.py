import json
import os
import logging

class ConfigManager:
    DEFAULT_CONFIG_PATH = os.path.join("config", "settings.json")
    DEFAULT_CONFIG = {
        "nas": {
            "address": "",
            "username": "",
            "password": ""
        },
        "jobs": []
    }

    def __init__(self, config_path=None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self.DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger(__name__)
        self.load_config()

    def load_config(self):
        """Load configuration from the JSON file."""
        if not os.path.exists(self.config_path):
            self.logger.info(f"Config file not found at {self.config_path}. Creating default.")
            self.save_config()
            return

        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            self.logger.info("Configuration loaded successfully.")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON config: {e}. Using defaults.")
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")

    def save_config(self):
        """Save current configuration to the JSON file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            self.logger.info("Configuration saved successfully.")
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")

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
