# k_backups: Windows Backup Utility

`k_backups` is a Windows desktop backup tool that syncs local folders to a **Synology NAS** (over SMB) or a **local/USB drive**, tracks file state locally, and supports full restore back to your PC.

## Latest Features

- **Incremental sync engine (upload + delete):**
	- Detects new/changed files and uploads only what changed.
	- Detects local deletions and removes matching files from destination.
	- Uses size + mtime comparison with tolerance for SMB/FAT timestamp differences.

- **SQLite manifest tracking:**
	- Stores per-job file state in `config/manifest.db`.
	- Tracks `file_path`, `rel_path`, `size`, and `mtime` for differential backups.

- **Per-job state snapshot ZIPs:**
	- At the end of each successful backup job, the app creates a ZIP snapshot containing:
		- `config/settings.json`
		- `config/manifest.db`
	- The ZIP is uploaded into that job's destination folder on the NAS.
	- Retention policy: only the most recent snapshot ZIP for that job is kept (older job snapshots are deleted).
	- Snapshot filename format: `_k_backups_snapshot_<job_name>_<timestamp>.zip`

- **Local and NAS destinations:**
	- Backs up to a Synology NAS over SMB (UNC path, e.g. `\\DiskStation\share\folder`).
	- Backs up to a local or USB/external drive (drive letter path, e.g. `E:\backups`).
	- Destination type is detected automatically — no NAS credentials needed for local drives.

- **Multi-source backup jobs:**
	- Each job can include multiple source folders.
	- Source folder names are preserved at destination with collision-safe naming (e.g., `Docs`, `Docs_2`).
	- Jobs can be added, edited, and deleted from the GUI.

- **Backup controls in Dashboard:**
	- Start backup with live progress updates.
	- **Pause / Resume** running jobs.
	- **Stop** currently running jobs safely.

- **Restore workflow:**
	- Full restore by job from NAS to a local folder.
	- Recreates directory structure from the stored manifest.

- **OneDrive placeholder hydration:**
	- Detects OneDrive placeholders and attempts to hydrate before upload.
	- Skips file upload when hydration fails and continues remaining operations.

- **Improved configuration handling:**
	- Canonical settings file: `config/settings.json`.
	- Auto-migrates legacy root `settings.json` to `config/settings.json`.
	- On invalid JSON, preserves broken file as `config/settings.json.invalid` and regenerates defaults.
	- Dashboard shows settings file path and last modified timestamp.

- **Windows reminder scheduling:**
	- Per-job reminder schedules managed from **Settings**.
	- Supports **Weekly** and **Monthly** recurrence.
	- Configurable enable/disable, time, weekly day, monthly day, task name, and custom reminder message.
	- Uses Windows Task Scheduler with console popup reminders (`msg`).
	- Reminder only (does not force automatic unattended backup execution).

- **Usability improvements:**
	- Dark-themed Tkinter UI.
	- Drag-and-drop source folder support (when `tkinterdnd2` is available).
	- Multi-folder picker support (when `tkfilebrowser` is available).

- **Logging & diagnostics:**
	- Rotating log file at `logs/backup_utility.log` (up to 3 backups, 5 MB each).
	- Console + file logging for troubleshooting.

## Requirements

- **OS:** Windows 10 or 11
- **Destination:** SMB-accessible share (Synology NAS supported)
- **Python (development mode):** 3.10+

## Installation (End Users)

This app is intended to be distributed as a **portable folder build**.

1. Download the latest release zip.
2. Extract to a folder (for example, `C:\Apps\k_backups`).
3. Launch the packaged executable from that folder.

## Development Setup

1. Run `setup_dev.bat`.
2. Start GUI with:

	 ```bash
	 python main.py
	 ```

3. Optional CLI run (executes first configured job):

	 ```bash
	 python run_cli.py
	 ```

4. Build packaged app:

	 ```bash
	 build.bat
	 ```

## Schedule Smoke Test

Run the reusable scheduler smoke test (create/disable/remove) from repo root:

```powershell
.\scripts\smoke_schedule.ps1 -Mode both
```

Modes:
- `-Mode weekly`
- `-Mode monthly`
- `-Mode both`

## Configuration Files

- `config/settings.json` – NAS settings and job definitions
- `config/manifest.db` – SQLite file manifest for incremental sync
- `logs/backup_utility.log` – runtime log output

## Quick Usage

1. Open **Settings** tab and enter NAS address (UNC), username, and password.
2. Open **Manage Jobs** and create at least one job (name, source folder(s), destination folder).
3. Open **Dashboard**, select a job, and click **Backup Now**.
4. Use **Pause**, **Resume**, or **Stop** while a backup is running.
5. Use **Restore** tab to restore a job to a local destination folder.

## Notes & Current Scope

- Exclude patterns are supported by the engine/config, but the current GUI does not expose exclude editing yet.
- Restore is job-level full restore using manifest entries.
- Credentials are stored in local settings JSON (plain text).

---
Built with Python + Tkinter.
