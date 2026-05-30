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

---

## Open Tasks (carried to CLAUDE.md)

The two remaining items above are also tracked in `CLAUDE.md` under **Open Tasks** and in `docs/feedback.md`.
