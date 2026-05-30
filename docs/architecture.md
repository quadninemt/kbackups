# k_backups — Architecture & Design Reference

This document captures the design intent, backup strategy, feature spec, and UI conventions for the k_backups project. It complements `CLAUDE.md` (operating rules) and `README.md` (user docs).

---

## High-Level Features

- User selects folders to include and exclude from backup.
- Backups sent to a Synology NAS over SMB.
- Configuration stores NAS connection info (address, credentials, share path).
- Simple dark-mode GUI for configuration and status.
- Manual backup execution (no unattended auto-backup — NAS is often powered off).
- Windows Task Scheduler reminders (weekly or monthly) to prompt the user to run a backup.
- Restore files from NAS back to local machine.
- Error handling and rotating log file.

---

## Backup Jobs

Each backup job specifies:
- **What**: included source folders, excluded patterns
- **Where**: NAS destination path (UNC)
- **When**: optional reminder schedule (weekly/monthly)
- **How**: incremental (default)

Users can create, edit, delete, and run jobs independently (e.g., documents weekly, photos monthly).

---

## Backup Strategy

**Incremental sync** — only new, changed, or deleted files are transferred.

### Algorithm

1. Scan local source folders → build current file list (path, size, mtime)
2. Load manifest from `config/manifest.db` → last known file state per job
3. Diff:
   - File in local but not in manifest → **upload** (new)
   - File in local and manifest, but size or mtime changed → **upload** (changed)
   - File in manifest but not local → **delete** from NAS (deleted locally)
   - File unchanged → **skip**
4. Execute uploads and deletes
5. Update manifest with new state
6. Upload snapshot ZIP (`settings.json` + `manifest.db`) to NAS destination
7. Remove older snapshot ZIPs for the job (keep only the latest)

### mtime Tolerance

Use a 2-second tolerance when comparing mtimes to handle FAT/SMB timestamp rounding differences.

### Multi-Source Jobs

Each source folder maps to a stable top-level folder name at the destination (e.g., `Documents`, `Pictures`). Collision-safe naming appends `_2`, `_3` etc. if two sources share a basename.

---

## OneDrive Integration

- Detect OneDrive placeholder files via Windows reparse point / file attribute flags.
- Trigger hydration by attempting to read the file — Windows downloads it on access.
- Do **not** use Microsoft Graph API — filesystem only.
- If hydration fails, skip the file and log a warning; continue with remaining files.

---

## Configuration & Manifest Storage

| File | Purpose |
|---|---|
| `config/settings.json` | NAS credentials + job definitions (plain text JSON) |
| `config/manifest.db` | SQLite — per-job file state (`file_path`, `rel_path`, `size`, `mtime`) |
| `logs/backup_utility.log` | Rotating log (5 MB × 3 backups) |

**Settings migration:** on startup, if legacy `settings.json` exists in app root and `config/settings.json` is missing, auto-migrate. If JSON is invalid, preserve as `.invalid` and regenerate defaults.

---

## Snapshot ZIPs

At the end of each successful job:
- Create `_k_backups_snapshot_<job>_<timestamp>.zip` containing `settings.json` + `manifest.db`
- Upload to the job's NAS destination folder
- Delete older snapshot ZIPs for that job (retention = 1)

This allows recovery of job configuration and manifest from the NAS if the local machine is lost.

---

## User Interface

- Tkinter with Azure Dark theme (`assets/azure.tcl`). Fallback to clam theme with manual dark styling if theme file is absent.
- 4 tabs: **Dashboard**, **Manage Jobs**, **Settings**, **Restore**
- Drag-and-drop source folder support (optional `tkinterdnd2`)
- Multi-folder picker (optional `tkfilebrowser`)

### Dashboard Tab
- Job selector combobox
- Backup Now / Pause / Resume / Stop buttons
- Four stat cards (replacing the old progress bar): **% Complete**, **Backed Up**, **Up to Date** (skipped), **Failed** (⚠ when > 0). Fed live from `BackupEngine.stats`.
- Status label
- Settings file path and last-modified status
- Scrolled activity log

### Manage Jobs Tab
- Treeview listing jobs (name, source paths, destination)
- Add / Edit / Delete job dialogs (600×600 modal)
- Source folder listbox with Add Folder / Remove Selected / drag-and-drop

### Settings Tab
- NAS Connection: address (UNC), username, password
- Per-job reminder schedule: recurrence (weekly/monthly), time, day, task name, message
- Save Schedule / Remove Schedule buttons

### Restore Tab
- Job selector
- Local restore destination picker
- Start Full Restore button

### Sample Layout

```
+-------------------------------------------------------------+
|                k_backups - Backup Utility                   |
+--[Dashboard]--[Manage Jobs]--[Settings]--[Restore]----------+
|                                                             |
|  Select Job: [ combo ]   [ Backup Now ] [ Pause ] [ Stop ] |
|  [============================] progress bar                |
|  Status: Ready                                              |
|  ---------------------------------------------------------- |
|  Settings File: config/settings.json | Last updated: ...   |
|  ---------------------------------------------------------- |
|  Activity Log:                                              |
|  Uploading Documents\report.pdf...                          |
|  Deleting old_file.txt...                                   |
|  Backup completed successfully.                             |
+-------------------------------------------------------------+
```

---

## Destination Types

The backup engine auto-detects which connector to use based on the destination path format:

| Destination format | Connector | NAS credentials |
|---|---|---|
| `E:\backups`, `C:\folder\` (drive letter) | `LocalConnector` — uses `shutil.copy2` + `os` | Not required |
| `\\DiskStation\share\folder` (UNC path) | `ShareConnector` — uses `smbclient` | Required |

`LocalConnector` supports USB drives, external hard drives, and any locally-mounted path. It preserves file metadata (timestamps) via `shutil.copy2`. All other engine behaviour (incremental sync, manifest, snapshots, pause/stop) is identical for both connector types.

## Auto-Update (`src/updater.py`)

The app can update itself from GitHub Releases.

**Check:** `GET https://api.github.com/repos/quadninemt/kbackups/releases/latest` (no auth — public repo). Compares the release `tag_name` (e.g. `v1.2.0`) against the running `__version__` using tuple-based semver comparison. Triggered silently ~2.5s after startup (non-blocking thread) and manually via the **Check for Updates** button in Settings.

**Download:** Streams the release's `.zip` asset to `%TEMP%\k_backups_update.zip` with progress reporting.

**Apply (self-replace):** Windows locks the running exe, so the update cannot overwrite it directly. Instead the updater:
1. Extracts the ZIP to a temp dir.
2. Writes a helper `.bat` to `%TEMP%` that: waits for the app to exit (polls `tasklist` filtered by **PID *and* image name** — robust against PID reuse) → `robocopy` the new files over the app dir with **limited retries (`/R:5 /W:2`)** → relaunches `BackupUtility.exe` → cleans up. Every step (including the robocopy exit code) is appended to `update_helper.log` in the app folder.
3. Launches the helper detached (`DETACHED_PROCESS`, hidden) and closes the app.

**Helper hardening (learned the hard way):**
- **Limited robocopy retries** — the default is 1,000,000 retries × 30s wait, so a locked/AV-blocked exe makes the helper hang forever. `/R:5 /W:2` caps it (~10s) and then logs the failure.
- **Space before every `>`/`>>`** — a token like `%RC%>>file` where `RC` is a digit is parsed by cmd as a stream-handle redirect (`1>>`), silently eating the value. All redirections are spaced.
- **On copy failure** the old version is retained and the app is still relaunched, so the user is never left without a working app; `update_helper.log` records why (commonly Avast blocking writes to the install folder).
- The buggy first-generation helper shipped in v1.2.0/v1.3.0; fixing it required a **one-time manual install** of v1.3.1+, after which auto-update works.

**Constraints:**
- Only runs in the packaged (`sys.frozen`) app; in dev mode it tells the user to `git pull`.
- Each GitHub Release must have a `.zip` asset containing the full dist (`BackupUtility.exe` + `_internal/`).
- AV (Avast) may quarantine the downloaded/extracted exe; the install folder may need an AV exception.
- `config/` and `logs/` live alongside the exe and are never touched by `robocopy` of the new dist (the ZIP contains only program files).

## Packaging

- PyInstaller **folder-based** distribution (not single-file exe) — faster startup, cleaner deps.
- Output: `dist/k_backups_dist/BackupUtility.exe` + supporting files.
- Must be self-contained — end user needs no Python installation.
- Spec file: `k_backups.spec`

---

## Resilient Upload / Retry

Uploads are fault-tolerant to handle slow or failing OneDrive hydration and transient network errors:

1. **First pass** — attempt every upload. OneDrive hydration failures are treated as upload failures (not silent skips). Failures are logged with the full path and collected into a retry queue; the run continues.
2. **Retry passes** — the failed queue is retried up to `MAX_UPLOAD_RETRIES` (default 2) times, with a `RETRY_BACKOFF_SECONDS` (default 3s) wait between passes and re-hydration each attempt. Pause/Stop are honoured throughout.
3. **Persistent failures** — files still failing after all retries are logged at WARNING (each path listed) and exposed via `BackupEngine.last_run_failures`. They are **not** written to the manifest, so the next backup retries them naturally.

The job still returns success (it ran to completion); the GUI reads `last_run_failures` and shows a "completed with N errors" warning dialog listing the affected paths instead of a plain success message. The final log line summarises uploaded vs. failed counts.

## Manifest Batch Write Strategy

Manifest updates are accumulated in memory during a backup run and flushed in two batch transactions at the end (one for deletes, one for inserts/updates via `executemany`). This avoids per-file connection open/close overhead on large jobs.

Trade-off: if a job is killed mid-run, the manifest won't reflect partial progress. On the next run, files uploaded during the killed run will be re-uploaded. This is acceptable for a personal backup tool.

---

## Known Limitations / Open Design Items

- Credentials stored plain text in `config/settings.json` — acceptable for local personal tool, noted in README.
- Exclude patterns are supported by engine and config schema but not yet exposed in the Add/Edit Job GUI.
- Restore is job-level full restore only (no selective file restore).
- No automatic unattended backup execution — reminders only, by design (NAS may be off).
- `ShareConnector.list_files()` is non-recursive — sufficient for snapshot cleanup (snapshots are top-level in the job folder) but not for general directory walking.
