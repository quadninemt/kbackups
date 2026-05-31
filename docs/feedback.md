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

### [DONE] exe icon still shows the wrong icon (not the new Quadnine logo)
Diagnosed: the correct multi-resolution icon IS embedded in the binary (valid ICO,
6 sizes incl. 256×256; exe built after the icon was generated). The stale icon is
the **Windows icon cache**, which keys off the exe path and doesn't refresh on file
change. Fix on the user's side: clear the icon cache (`ie4uinit.exe -show` then
restart Explorer) or deploy to a fresh folder name. v1.3.0 build confirmed to embed
the icon. No code change required.

### [DONE] Settings page too long — items hidden below the fold
Wrapped the entire Settings tab in a scrollable Canvas + scrollbar (mousewheel bound
while hovering). All sections — NAS, Schedule, and Application Updates — are now
reachable regardless of window height.

### [DONE] v1.2 auto-update gave no "new version" alert
Two causes, both resolved: (a) when v1.2.0 ran it WAS the latest release, so the
silent startup check correctly stayed quiet (by design it only alerts when a newer
version exists); (b) the repo was still **private** at that moment, so the API call
404'd silently. Repo is now public and v1.3.0 will be published — the running v1.2.0
will detect and offer it on next launch.

### [DONE] No visible "Check for Updates" button
The button existed but sat below the fold on the overlong Settings tab (same root
cause as the settings-length item). It's now reachable thanks to the scrollable
Settings tab.

### [DONE] Auto-update ran but didn't actually update (v1.2/v1.3.0)
Diagnosed from leftover artifacts (helper .bat + extract dirs persisted; installed
exe stayed at the v1.2 size). Root causes in the first-gen helper:
(1) `robocopy` used default retries (1,000,000 × 30s) so a locked/AV-blocked exe
made it hang forever and never replace the file; (2) the PID-wait matched the raw
PID number anywhere in `tasklist` output (fragile on PID reuse); (3) no logging, so
failures were invisible. Rewrote the helper: waits on PID **and** image name,
`robocopy /R:5 /W:2`, full logging to `update_helper.log` in the app folder, retains
old version + relaunches on failure. Validated the copy/exit-code logic in a sandbox.
NOTE: the broken helper is baked into v1.2.0/v1.3.0 — fix requires a **one-time manual
install of v1.3.1**; auto-update works from there. If Avast blocks writes to the
install folder, add that folder to Avast exceptions.

### [DONE] Add Deleted card; clarify "Up to Date" (it's not always 0)
Added a fifth dashboard card, **Deleted** (amber), so all three scan-result figures
are cards: Backed Up / Up to Date / Deleted (plus % Complete and Failed). Engine now
tracks `stats['deleted']`. Confirmed via a 4-run sandbox that "Up to Date" is only 0
on the *first* backup (empty manifest); on re-runs it correctly counts unchanged
files (run2: 0 backed up / 5 up to date; run3: 1 changed / 4 up to date). "files
found" during scan = files on disk (filesystem), before the manifest diff. (v1.3.5)

### [DONE] No feedback during the initial file scan
On "Backup Now" the engine scans all source files (to skip unchanged ones) before
any progress showed — looked frozen on large OneDrive trees, and the skip outcome was
never surfaced. Now: `FileScanner.scan` takes a progress callback and reports every
~1000 files; the engine logs "Scanning: <folder>", live "Scanning <folder>… N files
found", "Scanned N files in <folder>", "Scan complete: N files total", and a summary
"Scan result: X to back up, Y up to date, Z to delete". Activity-log filter broadened
so all of these appear. (v1.3.4)

### [DONE] Auto-update helper died on app exit (v1.3.1/1.3.2) — visible cmd window, no update
The helper got stuck at the process-wait and was killed when the app exited (log
stopped at "waiting for PID … to exit"; installed exe stayed v1.3.1). Root cause:
the app runs inside a Windows **Job Object with kill-on-close**, which also kills a
merely-detached child. Secondary bug: `timeout` needs stdin, which a detached helper
lacks, so it aborted. Fix (v1.3.3): launch the helper with `CREATE_BREAKAWAY_FROM_JOB`
(+ new process group, no window, DEVNULL handles) with a fallback, so it truly
outlives the app; replaced `timeout` with `ping`-based sleeps. Survival validated in
a sandbox (helper wrote its marker 3s after the launcher exited; breakaway=True).
NOTE: the broken launcher is in v1.3.1/1.3.2 too → requires one more **manual install
of v1.3.3**; auto-update works from there.

### [DONE] Dashboard: four stat indicators instead of the progress bar
Replaced the progress bar with four color-accented stat cards: **% Complete**
(blue), **Backed Up** (green), **Up to Date / skipped** (gray), **Failed** (red, with
a ⚠ glyph when > 0). Engine now tracks live counts via `BackupEngine.stats`
(`backed_up`, `skipped`, `failed`); the GUI reads them in the progress callback and
updates the cards live. Cards reset to 0 at the start of a run and retain final
totals afterward (per user preference). `run_cli.py` is unaffected (callback
signature unchanged).

### [DONE] Change the Failed card text to yellow
Failed card value + accent are now yellow (`#f1c40f`) instead of red. (v1.3.6)

### [DONE] Failed card showed 4k+ but dialog said "no files failed"
The card read the live `stats['failed']` during the run, but the dialog read
`self.last_failures`, which was only set in `cleanup()` *after* `run_job` returned —
so clicking mid-run (or after an early Stop) showed an empty list, and a large count
(e.g. 4k, typically a systemic failure like an unreachable destination) had no detail.
Fix (v1.3.7): the engine now maintains failures **live** in a thread-safe map
(`_failures`), exposed via the `last_run_failures` property; the dialog reads the live
engine when a run is in progress and falls back to the captured list afterward. Card
count and dialog list are now always consistent. Verified: a 6-file all-fail run gives
`stats.failed == 6` and 6 `{path,error}` entries.

### [DONE] Click the Failed card → dialog of failed files + error messages
The Failed card is now clickable (hand cursor) and opens a scrollable dialog listing
each failed file path with its error message. `BackupEngine.last_run_failures` now
stores `{path, error}` dicts (last failure reason tracked through the retry loop); the
GUI remembers the run's failures in `self.last_failures` so the dialog works after the
run ends. Clicking with no failures shows a friendly "no files failed" message. (v1.3.6)

