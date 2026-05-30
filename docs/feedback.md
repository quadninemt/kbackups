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

### [OPEN] Resilient backup for flaky OneDrive/network files
Many backups pull from OneDrive; connections can be slow or fail. The app should:
log each file failure (with path), continue, then retry failed files at the end.
Files that still fail after retries must be recorded in the backup log.
(User open to better suggestions — see proposed plan in chat.)