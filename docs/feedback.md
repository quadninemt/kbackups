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
