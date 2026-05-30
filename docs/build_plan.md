# Build Plan: k_backups

Development progress tracker. Completed phases are archived here for reference.

---

## Phase 1: Project Setup & Infrastructure
- [x] Initialize project structure (`src`, `assets`, `config`, `tests`)
- [x] Environment setup (`requirements.txt`, virtual environment)
- [x] `ConfigManager` — load/save JSON settings (NAS credentials, jobs)
- [x] Logger — rotating file + console output

## Phase 2: Core Backup Engine
- [x] NAS connectivity (`share_connector.py` via `smbprotocol`)
- [x] File scanner — walk local dirs, respect exclude patterns
- [x] OneDrive hydration — detect placeholders, trigger download before upload
- [x] Manifest system (`ManifestManager`, SQLite)
- [x] Differential logic — identify new, changed, deleted files
- [x] File transfer — upload/delete to NAS
- [x] Core usage test — CLI runner without GUI

## Phase 3: User Interface (Tkinter)
- [x] Main window with Azure Dark theme
- [x] NAS configuration tab
- [x] Job manager UI (Add, Edit, Delete)
- [x] Backup status view (progress bar, log)
- [x] GUI ↔ BackupEngine integration (threaded, non-blocking)

## Phase 4: Scheduling & Restore
- [x] Restore logic (NAS → local)
- [x] Restore UI tab
- [x] Windows Task Scheduler reminder integration (`schtasks`)

## Phase 5: Packaging & Final Polish
- [x] Icon and assets in `assets/`
- [x] PyInstaller spec (`k_backups.spec`)
- [ ] **Build & Test**: Run `build.bat` and verify `BackupUtility.exe` on a clean machine (no Python installed)
- [ ] **Documentation**: Finalize README, clean up inline code comments

## Phase 6: Architecture Improvements
- [x] Fix `ManifestManager` path resolution — now uses `_get_default_db_path()` with `sys.frozen` support; removes `BackupEngine._resolve_manifest_db_path()` workaround
- [x] Fix `ShareConnector.disconnect()` — now stores `_server_name` at connect time and passes it correctly to `delete_session()`
- [x] Batch manifest writes — `batch_update_files()` / `batch_remove_files()` using `executemany` in single transactions; backup engine accumulates and flushes at end of job
- [x] Fix progress callback operator precedence bug in `main_window.py`
- [x] Pin versions in `requirements.txt` (`smbprotocol~=1.13`, `pyinstaller>=6.3`, etc.)
- [x] Make `tkinterdnd2` hidden import conditional in `k_backups.spec`
- [x] Fix `build.bat` — only pause on error
- [x] Add job-name argument to `run_cli.py` (`python run_cli.py [job-name]`)
- [x] Add `__version__ = "1.0.0"` to `src/__init__.py`; show in window title

---

## Open Tasks (carried to CLAUDE.md)

The two remaining items above are also tracked in `CLAUDE.md` under **Open Tasks** and in `docs/feedback.md`.
