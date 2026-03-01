# Build Plan: k_backups

This document outlines the step-by-step plan to build the `k_backups` utility. AI agents should follow this order, marking tasks as completed `[x]` after testing and verification.

## Phase 1: Project Setup & Infrastructure
- [x] **Initialize Project Structure**: Create `src`, `assets`, `config`, `tests` folders.
- [x] **Environment Setup**: Create `requirements.txt` (include `tk`, `smbprotocol`, `pyinstaller`, etc.) and set up a development virtual environment.
- [x] **Config Manager**: Implement a `ConfigManager` class to load/save JSON settings (NAS credentials, jobs).
- [x] **Logger**: Set up a logging module to write to both console (dev) and a log file.

## Phase 2: Core Backup Engine
- [x] **NAS Connectivity**: Implement `share_connector.py` using `smbprotocol` to test connection and list files on the NAS.
- [x] **File Scanner**: Create a scanner that walks local directories, respecting exclude patterns.
- [x] **OneDrive Hydration**: Implement a function to detect OneDrive placeholders and trigger Windows hydration (read file) before backup.
- [x] **Manifest System**: Implement `ManifestManager` to read/write the local state (JSON/SQLite).
- [x] **Differential Logic**: Implement the comparison logic (Local vs Manifest) to identify New, Changed, and Deleted files.
- [x] **File Transfer**: Implement the actual upload/delete functions to the NAS.
- [x] **Core Usage Test**: Write a script to simulate a backup run without the GUI.

## Phase 3: User Interface (Tkinter)
- [x] **Main Window Frame**: Create the main Tkinter window with the "Azure Dark" theme setup.
- [x] **NAS Configuration Tab**: Build the form for entering and testing NAS credentials.
- [x] **Job Manager UI**: Create the interface to Add, Edit, and Delete backup jobs (source, destination, excludes).
- [x] **Backup Status View**: Implement the progress bar and status log display.
- [x] **Integration**: Connect the GUI buttons (Backup Now) to the Core Backup Engine running in a separate thread (to keep UI responsive).

## Phase 4: Scheduling & Restore
- [x] **Restore Logic**: Implement the logic to copy files *from* NAS back to PC.
- [x] **Restore UI**: Add the "Restore" tab to the interface.
- [x] **Task Scheduler Integration**: Implement the "Create Reminder" button that uses `schtasks` (Windows Command) to add a monthly notification task.

## Phase 5: Packaging & Final Polish
- [x] **Icon & Assets**: Ensure all theme files and icons are in `assets/`.
- [x] **PyInstaller Spec**: Create the `.spec` file for a folder-based build.
- [ ] **Build & Test**: Run the build process and test the resulting `BackupUtility.exe` on a fresh path.
- [ ] **Documentation**: Finalize README and cleanup code comments.
