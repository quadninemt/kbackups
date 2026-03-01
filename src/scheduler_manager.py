import subprocess
import logging
import sys
import os

class SchedulerManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_monthly_reminder(self, task_name="k_backups_reminder"):
        """
        Creates a Windows Scheduled Task that runs this application monthly.
        """
        # Get path to current executable
        if getattr(sys, 'frozen', False):
            executable_path = sys.executable
        else:
            # If running from source, use python executable + script?
            # Or just assume development context.
            executable_path = sys.executable + ' ' + os.path.abspath(sys.argv[0])

        # Quote path properly
        # executable_path might contain spaces
        path_quoted = f'\\"{executable_path}\\"' 
        
        # schtasks /Create /F /SC MONTHLY /TN "TaskName" /TR "Path" /ST 09:00
        # Note: /F forces overwrite
        cmd = f'schtasks /Create /F /SC MONTHLY /TN "{task_name}" /TR "{path_quoted}" /ST 09:00'
        
        self.logger.info(f"Creating scheduled task: {cmd}")
        
        try:
            # using shell=True to handle quoting easier
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                self.logger.info("Daily reminder task created successfully.")
                return True
            else:
                self.logger.error(f"Failed to create task: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error creating task: {e}")
            return False

    def remove_reminder(self, task_name="k_backups_reminder"):
        cmd = f'schtasks /Delete /F /TN "{task_name}"'
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                self.logger.info("Task deleted successfully.")
                return True
            else:
                self.logger.warning(f"Failed to delete task (maybe didn't exist): {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error deleting task: {e}")
            return False
