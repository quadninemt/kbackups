# Feedback & Ideas

Add feedback, bugs, and feature ideas here. Claude will read this file at the start of each session, identify open items, prepare a plan, and ask for confirmation before acting.

## Format

Use this structure for each item:

```
### [OPEN] Short title
Description of the issue, idea, or request.

### [DONE] Short title
What was done.
```

---

## Items

<!-- Add your feedback below this line -->

### [DONE] Backup to USB/local drive fails with empty NAS settings
Destination `E:\backups` is a local path but the engine required NAS credentials.
Added `LocalConnector` (uses `shutil.copy2` / `os` calls) and auto-detection in
`BackupEngine` — if destination starts with a drive letter (`E:\`, `C:\`, etc.) it
uses `LocalConnector` and ignores NAS settings. UNC paths (`\\server\share`) still
use `ShareConnector`. 11 tests pass.

### [DONE] Use the new Quadnine logo as the app icon
Converted `assets/Quadnine_logo.png` (500×500) into a multi-resolution
`assets/app_icon.ico` (overwriting the old icon). Both the window icon and the
PyInstaller exe icon already reference `assets/app_icon.ico`, so no code/spec
changes were needed. Removed the stale root `icon.png` (old branding, unused).

### [DONE] Resilient backup for flaky OneDrive/network files
First pass logs each failure (with path) and continues; failed files (including
OneDrive hydration failures) are retried up to 2× with a 3s backoff. Files still
failing after retries are logged at WARNING (full paths) and surfaced in the GUI as
a "completed with N errors" dialog. Failures aren't written to the manifest, so the
next backup retries them. Added `_upload_one` + retry loop in `BackupEngine`,
`last_run_failures`, and 5 tests (16 total, all passing).