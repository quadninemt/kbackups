# AI Coding Agent Reference

This file serves as a reference for AI coding agents working on this project. It includes guidelines, conventions, and important notes relevant to automated or AI-assisted development in this workspace.

## Project Overview
The project will create a backup utility for users to back up files on their computers to a NAS. It will be written in Python, have a simple interface built with Tkinter, and will be packaged for Windows using PyInstaller.

## Coding Guidelines
- Use Python and Tkinter for all development.
- No strict style or naming conventions, but keep the code simple and compatible with as many Windows machines as possible.
- **NAS Connection:** 
  - Use the `smbprotocol` library (or similar) to connect to the NAS via SMB.
  - The destination will be specified in UNC format (e.g., `\\DiskStation\home\folder`).
  - Do not map network drives; connect directly using the library.
- **Config & Manifest Storage:**
  - Use **JSON** for storing configuration (including credentials in plain text for simplicity).
  - Use **JSON** or **SQLite** for the local file manifest.
- **Packaging:**
  - Use PyInstaller to create a **folder-based distribution** (not a single-file exe) to ensure faster startup and cleaner dependency management.
  - **Self-Contained:** The final output must not require the end user to have Python or any libraries installed.

## Directory Structure
- **src/**: Main source code (Python scripts, GUI logic).
- **assets/**: Theme resources (Azure Dark theme files).
- **config/**: User configuration files (JSON) and job definitions.
- **tests/**: Unit and integration tests.
- **requirements.txt**: Project dependencies.
- **main.py**: Entry point for the application.

## Automation & AI Agent Notes
- Keep the documentation updated.
- Always test your work before submitting changes.

## Contribution Process
- Always test before making changes.

## High-Level Features

- User can select files/folders to include in the backup.
- User can select files/folders to exclude from the backup.
- Backups are sent to a specified Synology NAS location.
- Configuration stores NAS connection information (e.g., address, credentials, share path).
- Simple GUI for configuration and status.
- Scheduled or manual backup options.
- Backup progress and status reporting.
- Error handling and logging.
- Restore files from backup.
- Add a Windows scheduled task (e.g., monthly) to remind the user if a backup has not been made.
  - This is a *reminder only*, not an automatic backup execution, because the NAS is often powered off.
- **OneDrive Integration:**
  - The utility will trigger the **Windows hydration process** (force download) for any file that is a placeholder. 
  - Do not use the Microsoft Graph API; interact with the filesystem directly.

## Backup Jobs

- The utility will support saving and managing multiple "backup jobs".
- Each backup job is a set of configurations specifying:
  - What to back up (included/excluded files and folders)
  - Where to back up (NAS location and connection info)
  - When to back up (schedule/frequency)
  - How to back up (options like incremental, full, etc.)
- Users can create, edit, delete, and run different backup jobs independently (e.g., main files weekly, photos monthly).
- The interface will provide a way to select and manage backup jobs.

## Backup Strategy

- Incremental backup: Only new, changed, or deleted files are synchronized with the NAS. Unchanged files are skipped.
- A local manifest (index) file records the state (hash/timestamp, size, path) of each file from the last backup.
- Before each backup, the current state is compared to the manifest:
  - New or changed files are uploaded.
  - Deleted files are removed from the NAS.
  - Unchanged files are skipped.
- After backup, the manifest is updated to reflect the new state.
- For files stored on OneDrive:
  - The utility detects OneDrive placeholders and automatically downloads files before backup.
  - Only the actual file (not the placeholder) is checked and recorded in the manifest.
  - This ensures OneDrive files are included in incremental backups without disrupting efficiency.

## User Interface

- The application will use a clean, clear interface in dark mode.
- Tkinter will be used for the GUI, with the "azure dark" theme applied for a modern dark appearance.
- Interface design principles:
  - Group related controls with clear labels and spacing.
  - Use modern fonts and avoid clutter.
  - Status and progress indicators should be easy to read.

## Sample Interface Layout

Below is a sample layout for the backup utility interface using the "azure dark" theme:

```
+-------------------------------------------------------------+
|                    Backup Utility (Dark Mode)               |
+-------------------------------------------------------------+
| [ Select Source Folders ]  [ Select Exclude Folders ]       |
|                                                             |
| [ List of Included Folders ]                                |
| [ List of Excluded Folders ]                                |
|-------------------------------------------------------------|
| NAS Connection: [ Address ] [ Username ] [ Password ] [Test] |
| NAS Share Path: [__________________________]                |
|-------------------------------------------------------------|
| [ Backup Now ]   [ Schedule Backup ]   [ Restore Files ]     |
|-------------------------------------------------------------|
| Status: [ Last backup date, progress bar, messages ]         |
+-------------------------------------------------------------+
```

- All controls and backgrounds use the "azure dark" color scheme.
- Controls are grouped for clarity: source/exclude, NAS config, actions, and status.
- Status bar at the bottom shows backup progress and messages.

---

*Update this file as the project evolves to keep AI agents aligned with best practices and project goals.*
