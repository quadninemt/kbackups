# k_backups: Windows to Synology NAS Backup Utility

A simple, efficient, and reliable backup tool designed for Windows users to safeguard their files by synchronizing them to a Synology NAS.

## Key Features

*   **Smart Incremental Backups**: Only uploads new, changed, or deleted files to save time and bandwidth.
*   **OneDrive Integration**: Automatically downloads (hydrates) OneDrive placeholders before backing them up, ensuring your cloud files are safe locally and on your NAS.
*   **Multiple Backup Jobs**: Create and manage different backup routines (e.g., "Weekly Documents", "Monthly Photos") with unique schedules and settings.
*   **Modern Dark Mode Interface**: Features a clean, easy-to-use GUI with the "Azure Dark" theme.
*   **Helpful Reminders**: Set up Windows scheduled tasks to remind you when it's time to run a manual backup.
*   **Privacy First**: Your NAS credentials and file manifests are stored locally on your machine.

## Requirements

*   **Operating System**: Windows 10 or 11.
*   **Storage**: A Synology NAS accessible via your local network (SMB).

## Installation

This application is distributed as a **portable folder**. There is no complex installer or need for Python/dependencies.

1.  Download the latest release zip file.
2.  Extract the folder to a location of your choice (e.g., `C:\Apps\k_backups`).
3.  Open the folder and run `BackupUtility.exe`.

## Settings File Location

The app stores and reads settings from:

*   `config/settings.json` (inside the app folder)

Behavior on startup:

*   If `config/settings.json` exists, it is loaded.
*   If only a legacy `settings.json` exists in the app root, it is automatically copied to `config/settings.json` on first run.
*   If the file is missing, a default `config/settings.json` is created.
*   If the file contains invalid JSON, the invalid file is preserved as `config/settings.json.invalid` and a new default `config/settings.json` is created.

## How to Use

### 1. Connecting to your NAS

On the main screen, enter your Synology NAS details:
*   **Address**: Use the UNC format (e.g., `\\DiskStation\home\backups`).
*   **Credentials**: Enter your NAS username and password.
*   **Test Connection**: Click to ensure the utility can access your shared folder.

### 2. Creating a Backup Job

*   Click **New Job** to start a configuration.
*   **Source**: Select the folders on your computer you want to back up.
*   **Exclude**: Optionally, choose specific subfolders or file types to skip.
*   **Save Job**: Give your job a name (e.g., "Personal Files").

### 3. Running a Backup

*   Select a job from the list.
*   Click **Backup Now**.
*   The status bar will show progress as files are analyzed and transferred.

### 4. Restoring Files

*   Go to the **Restore** tab.
*   Select the backup source and the destination on your PC.
*   Choose specific files or restore the entire directory.

## Troubleshooting

*   **OneDrive Files not backing up?** Ensure your computer is connected to the internet so placeholders can be downloaded.
*   **Connection Failed?** Check that your NAS is powered on and your computer is on the same network.

---
*Built with Python & Tkinter.*
