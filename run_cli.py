import sys
from src.config_manager import ConfigManager
from src.backup_engine import BackupEngine
from src.logger import setup_logger

def progress_report(processed, total, msg):
    percent = int((processed / total) * 100) if total > 0 else 0
    print(f"[{percent}%] {msg}")

def main():
    logger = setup_logger()
    config = ConfigManager()

    jobs = config.get_jobs()
    if not jobs:
        print("No jobs configured. Add a job via the GUI or edit config/settings.json.")
        return

    # Use job name from first CLI argument, or default to the first configured job
    job_name = sys.argv[1] if len(sys.argv) > 1 else jobs[0]['name']

    available = [j['name'] for j in jobs]
    if job_name not in available:
        print(f"Job '{job_name}' not found. Available jobs: {', '.join(available)}")
        sys.exit(1)

    print(f"Starting backup for job: '{job_name}'")
    engine = BackupEngine(config)
    success = engine.run_job(job_name, progress_callback=progress_report)
    print("Backup finished successfully." if success else "Backup failed.")
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
