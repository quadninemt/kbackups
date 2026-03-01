import sys
from src.config_manager import ConfigManager
from src.backup_engine import BackupEngine
from src.logger import setup_logger

def progress_report(processed, total, msg):
    percent = 0
    if total > 0:
        percent = int((processed / total) * 100)
    print(f"[{percent}%] {msg}")

def main():
    logger = setup_logger()
    config = ConfigManager()
    
    jobs = config.get_jobs()
    if not jobs:
        print("No jobs configured. Please add a job to config/settings.json manually or via GUI.")
        
        # Create a dummy job for testing if none exist?
        # Maybe prompt usage
        print("Usage: Run this script. If no jobs exist, add one to config/settings.json")
        print('Example job in config/settings.json:')
        print('  "jobs": [{"name": "TestBackup", "source_paths": ["C:\\\\MyFiles"], "exclude_patterns": [], "destination_path": "BackupOne"}]')
        return

    # Run the first job for testing
    job_name = jobs[0]['name']
    print(f"Starting backup for job: '{job_name}'")
    
    engine = BackupEngine(config)
    success = engine.run_job(job_name, progress_callback=progress_report)
    
    if success:
        print("Backup finished successfully.")
    else:
        print("Backup failed.")

if __name__ == "__main__":
    main()
