# Claude Code Configuration — k_backups

## Project Overview

`k_backups` is a Windows desktop backup utility (Python 3.10+ / Tkinter) that syncs local folders to a Synology NAS over SMB, tracks file state with SQLite for incremental sync, and supports full restore. Packaged as a portable Windows `.exe` via PyInstaller.

### Reference Docs

| File | Purpose |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Backup strategy, feature design, UI spec, known limitations |
| [`docs/build_plan.md`](docs/build_plan.md) | Development history and open tasks |
| [`docs/feedback.md`](docs/feedback.md) | User feedback and ideas — read at session start |
| [`README.md`](README.md) | End-user documentation (GitHub-facing) |

---

## Feedback Workflow

**At the start of every session**, always:
1. Read [`docs/feedback.md`](docs/feedback.md)
2. Identify all `[OPEN]` items
3. Prepare a plan covering those items
4. Ask the user to confirm before making any changes
5. Execute, then update feedback.md — change `[OPEN]` to `[DONE]` and summarise what was done

---

## Behavioral Rules (Always Enforced)

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they are absolutely necessary for the goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (`*.md`) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- Never continuously check status after spawning a swarm — wait for results
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or `.env` files

---

## File Organization

- NEVER save to the root folder — use the directories below
- `/src` — source code
- `/tests` — test files
- `/docs` — documentation and markdown files
- `/config` — configuration files
- `/scripts` — utility scripts
- `/assets` — theme files, icons
- `/examples` — example code

---

## Coding Guidelines

### Tech Stack
- **Language:** Python 3.10+
- **GUI:** Tkinter — Azure Dark theme (`assets/azure.tcl`); fallback to clam with manual dark styling
- **NAS:** `smbprotocol` library — connect directly via SMB, no mapped drives
- **Destination format:** UNC paths (e.g., `\\DiskStation\share\folder`)
- **Config:** JSON at `config/settings.json` (credentials plain text — acceptable for local personal tool)
- **Manifest:** SQLite at `config/manifest.db`
- **Packaging:** PyInstaller folder-based build (`k_backups.spec`) — not single-file exe

### Configuration Conventions
- Canonical settings path: `config/settings.json` (relative to app root, works in dev and packaged)
- On startup: auto-migrate legacy root `settings.json` → `config/settings.json`
- On invalid JSON: preserve as `config/settings.json.invalid`, regenerate defaults

### OneDrive
- Detect placeholders via Windows reparse point / file attribute flags
- Trigger hydration by attempting to read the file (Windows downloads on access)
- Do NOT use Microsoft Graph API — filesystem only
- If hydration fails: skip file, log warning, continue

### General
- Keep files under 500 lines
- Validate input at system boundaries (user input, file paths, external APIs)
- Sanitize file paths to prevent directory traversal
- No hardcoded credentials or secrets

---

## Build & Test

```bash
# Launch GUI (development)
python main.py

# Run first configured job via CLI
python run_cli.py

# Run tests
python -m pytest tests/

# Build portable exe
build.bat

# Scheduler smoke test
.\scripts\smoke_schedule.ps1 -Mode both
```

- ALWAYS run tests after making code changes
- ALWAYS verify build succeeds before committing

---

## Security Rules

- NEVER hardcode API keys, secrets, or credentials in source files
- NEVER commit `.env` files or any file containing secrets
- Always validate user input at system boundaries
- Always sanitize file paths to prevent directory traversal
- Run `npx @claude-flow/cli@latest security scan` after security-related changes

---

## Open Tasks

- [ ] **Build & Test**: Run `build.bat` and verify `BackupUtility.exe` on a clean machine (no Python installed)
- [ ] **Documentation**: Finalize README, clean up inline code comments
- [ ] **GUI — Exclude Patterns**: Expose exclude pattern editing in Add/Edit Job dialogs (engine already supports it via `exclude_patterns` in job config)

## Recently Completed

- Dashboard now 5 cards: % Complete / Backed Up / Up to Date / Deleted / Failed (`BackupEngine.stats` tracks deleted too). "Up to Date" is 0 only on first backup (empty manifest); meaningful on re-runs
- Scan-phase visibility: `FileScanner.scan` reports progress every ~1000 files; engine logs per-folder scan progress + a "X to back up / Y up to date / Z to delete" summary to the activity log
- Auto-update helper now survives app exit: launched with `CREATE_BREAKAWAY_FROM_JOB` (+ new group, no window) to escape kill-on-close Job Object; `ping` instead of `timeout` (no stdin when detached). v1.3.1/1.3.2 helper died on exit → needs one-time manual install of v1.3.3
- Dashboard stat cards (replaced progress bar): % Complete / Backed Up / Up to Date / Failed (⚠ when >0), fed live from `BackupEngine.stats`
- Hardened auto-update helper: limited robocopy retries (`/R:5 /W:2`, never hangs), PID+image-name wait, full logging to `update_helper.log`, retains old version on failure. First-gen helper (v1.2.0/v1.3.0) was buggy → needs one-time manual install of v1.3.1+
- Scrollable Settings tab (Canvas + scrollbar + mousewheel) so NAS/Schedule/Updates sections never hide below the fold; "Check for Updates" button now reachable
- App icon: correct Quadnine icon is embedded; stale-icon reports are Windows icon cache (clear with `ie4uinit.exe -show` + restart Explorer)
- Resilient uploads: failed files (incl. OneDrive hydration failures) retried up to 2× with backoff; persistent failures logged with paths and surfaced in GUI via `BackupEngine.last_run_failures`
- Auto-update from GitHub Releases: `src/updater.py` (check/download/self-replace via helper .bat); startup auto-check + "Check for Updates" button in Settings. Each release needs a `.zip` asset with the full dist.
- Local/USB drive support: `LocalConnector` added to `src/share_connector.py`; `BackupEngine` auto-selects connector based on destination path (drive letter = local, UNC = SMB)

- Fixed `ManifestManager` path resolution (`sys.frozen` support, removed `BackupEngine._resolve_manifest_db_path` workaround)
- Fixed `ShareConnector.disconnect()` server name bug
- Batch manifest writes via `executemany` — single transaction per job instead of per-file
- Fixed progress callback operator precedence in `main_window.py`
- Pinned versions in `requirements.txt`
- Conditional `tkinterdnd2` in `k_backups.spec`
- `build.bat` only pauses on error
- `run_cli.py` accepts optional job-name argument
- Added `__version__ = "1.0.0"` shown in window title

---

## Concurrency: 1 MESSAGE = ALL RELATED OPERATIONS

- All operations MUST be concurrent/parallel in a single message
- Use Claude Code's Agent tool for spawning agents, not just MCP
- ALWAYS spawn ALL agents in ONE message with full instructions via Agent tool
- ALWAYS batch ALL file reads/writes/edits in ONE message
- ALWAYS batch ALL Bash commands in ONE message

---

## Swarm Orchestration

- MUST initialize the swarm using CLI tools when starting complex tasks
- MUST spawn concurrent agents using Claude Code's Agent tool
- Never use CLI tools alone for execution — Agent tool agents do the actual work
- MUST call CLI tools AND Agent tool in ONE message for complex work

### 3-Tier Model Routing (ADR-026)

| Tier | Handler | Latency | Cost | Use Cases |
|------|---------|---------|------|-----------|
| **1** | Agent Booster (WASM) | <1ms | $0 | Simple transforms (var→const, add types) — Skip LLM |
| **2** | Haiku | ~500ms | $0.0002 | Simple tasks, low complexity (<30%) |
| **3** | Sonnet/Opus | 2-5s | $0.003-0.015 | Complex reasoning, architecture, security (>30%) |

### Swarm Configuration & Anti-Drift

```bash
npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

- ALWAYS use hierarchical topology for coding swarms
- Keep maxAgents at 6-8 for tight coordination
- Use `raft` consensus for hive-mind
- Run frequent checkpoints via `post-task` hooks
- Keep shared memory namespace for all agents

### Swarm Execution Rules

- ALWAYS use `run_in_background: true` for all Agent tool calls
- ALWAYS put ALL Agent calls in ONE message for parallel execution
- After spawning, STOP — do NOT add more tool calls or check status
- Never poll agent status repeatedly — trust agents to return
- When agent results arrive, review ALL results before proceeding

---

## Project Config

- **Topology**: hierarchical-mesh
- **Max Agents**: 15
- **Memory**: hybrid
- **HNSW**: Enabled
- **Neural**: Enabled

---

## V3 CLI Commands

| Command | Subcommands | Description |
|---------|-------------|-------------|
| `init` | 4 | Project initialization |
| `agent` | 8 | Agent lifecycle management |
| `swarm` | 6 | Multi-agent swarm coordination |
| `memory` | 11 | AgentDB memory with HNSW search |
| `task` | 6 | Task creation and lifecycle |
| `session` | 7 | Session state management |
| `hooks` | 17 | Self-learning hooks + 12 workers |
| `hive-mind` | 6 | Byzantine fault-tolerant consensus |

```bash
npx @claude-flow/cli@latest init --wizard
npx @claude-flow/cli@latest swarm init --v3-mode
npx @claude-flow/cli@latest memory search --query "authentication patterns"
npx @claude-flow/cli@latest doctor --fix
```

---

## Available Agents

**Core Development:** `coder`, `reviewer`, `tester`, `planner`, `researcher`
**Specialized:** `security-architect`, `security-auditor`, `memory-specialist`, `performance-engineer`
**Coordination:** `hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`
**GitHub:** `pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`

---

## Memory & Vector Search

| Tool | Description |
|------|-------------|
| `memory_store` | Store value with ONNX 384-dim vector embedding |
| `memory_search` | Semantic vector search by query |
| `memory_retrieve` | Get entry by key |
| `memory_search_unified` | Search across ALL namespaces (Claude + AgentDB + patterns) |
| `memory_import_claude` | Import Claude Code memories into AgentDB |
| `memory_bridge_status` | Show bridge health, vectors, SONA, intelligence |

```bash
npx @claude-flow/cli@latest memory store --key "pattern-auth" --value "JWT with refresh" --namespace patterns
npx @claude-flow/cli@latest memory search --query "authentication patterns"
```

---

## Key MCP Tools

| Category | Tools |
|----------|-------|
| **Memory** | `memory_store`, `memory_search`, `memory_search_unified` |
| **Swarm** | `swarm_init`, `swarm_status`, `swarm_health` |
| **Agents** | `agent_spawn`, `agent_list`, `agent_status` |
| **Hive-Mind** | `hive-mind_init`, `hive-mind_spawn`, `hive-mind_consensus` |
| **Hooks** | `hooks_route`, `hooks_session-start`, `hooks_post-task` |
| **Security** | `aidefence_scan`, `aidefence_is_safe` |

Use `ToolSearch("keyword")` to discover available MCP tools.

---

## Quick Setup

```bash
claude mcp add claude-flow -- npx -y @claude-flow/cli@latest
npx @claude-flow/cli@latest daemon start
npx @claude-flow/cli@latest doctor --fix
```
