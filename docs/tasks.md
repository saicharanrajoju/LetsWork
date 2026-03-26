# LetsWork — Task Tracker (tasks.md)
*Single source of truth for what is done, what is next, and what is blocked.
Updated after every session. Read this at the start of every session.*

---

## Completed
- [x] CLAUDE.md written — project brain, rules, architecture overview
- [x] WORKFLOW.md written — exact build workflow, dual instruction system, task size rules
- [x] GitHub repo created — https://github.com/saicharanrajoju/LetsWork
- [x] docs/spec.md written — full product spec (10 sections, 7 MCP tools, 3 CLI commands, security, error handling)

## In Progress
- [ ] docs/tasks.md — this file (being created now)

## Next

### Phase 1 — Project Skeleton
- [ ] T-01: pyproject.toml — File: `pyproject.toml` — project metadata, dependencies (mcp, cloudflared-python, click), entry points for CLI
- [ ] T-02: src/__init__.py — File: `src/__init__.py` — empty init file, makes src a Python package
- [ ] T-03: src/cli.py scaffold — File: `src/cli.py` — import click, create the CLI group `@click.group()` named `letswork`, no commands yet, just the group
- [ ] T-04: README.md initial — File: `README.md` — project title, one-paragraph description, "coming soon" install instructions, license badge

### Phase 2 — Auth Module
- [ ] T-05: auth.py — generate_token — File: `src/auth.py` — function `generate_token() -> str` that creates a 32-char URL-safe random token using `secrets.token_urlsafe`
- [ ] T-06: auth.py — validate_token — File: `src/auth.py` — function `validate_token(provided: str, expected: str) -> bool` that does constant-time comparison using `hmac.compare_digest`
- [ ] T-07: test_auth.py — File: `tests/test_auth.py` — test `generate_token` returns 32+ chars, test `validate_token` with correct and incorrect tokens

### Phase 3 — File Locking Module
- [ ] T-08: filelock.py — LockManager class — File: `src/filelock.py` — class `LockManager` with `__init__(self)` that creates an empty dict `self._locks: dict[str, str]` (path -> user_id)
- [ ] T-09: filelock.py — acquire_lock — File: `src/filelock.py` — method `acquire_lock(self, path: str, user_id: str) -> bool` — returns True if path not in locks or already owned, adds to dict
- [ ] T-10: filelock.py — release_lock — File: `src/filelock.py` — method `release_lock(self, path: str, user_id: str) -> bool` — returns True if lock existed and was owned by user_id, removes from dict
- [ ] T-11: filelock.py — get_locks — File: `src/filelock.py` — method `get_locks(self) -> dict[str, str]` — returns copy of current locks dict
- [ ] T-12: filelock.py — is_locked — File: `src/filelock.py` — method `is_locked(self, path: str) -> tuple[bool, str | None]` — returns (True, user_id) if locked, (False, None) if not
- [ ] T-13: test_filelock.py — File: `tests/test_filelock.py` — tests for acquire, release, get_locks, is_locked, conflict scenario (two users same file)

### Phase 4 — MCP Server Foundation
- [ ] T-14: server.py — create FastMCP app — File: `src/server.py` — import FastMCP from mcp, create `app = FastMCP("letswork")`, instantiate `LockManager`, store `token` and `project_root` as module-level vars
- [ ] T-15: server.py — auth middleware helper — File: `src/server.py` — function `check_auth(provided_token: str) -> bool` that calls `validate_token` against stored token, raises error if invalid

### Phase 5 — MCP Tools (one task per tool)
- [ ] T-16: server.py — list_files tool — File: `src/server.py` — MCP tool `list_files(path: str = ".")` that returns directory listing of project_root/path using `os.listdir`, with lock status for each file
- [ ] T-17: server.py — read_file tool — File: `src/server.py` — MCP tool `read_file(path: str)` that reads and returns file content from project_root/path, checks file exists, max 1MB size limit
- [ ] T-18: server.py — write_file tool — File: `src/server.py` — MCP tool `write_file(path: str, content: str, user_id: str)` that acquires lock, writes content, keeps lock. Rejects if locked by another user
- [ ] T-19: server.py — lock_file tool — File: `src/server.py` — MCP tool `lock_file(path: str, user_id: str)` that explicitly locks a file without writing. Returns success/failure
- [ ] T-20: server.py — unlock_file tool — File: `src/server.py` — MCP tool `unlock_file(path: str, user_id: str)` that releases a lock. Only owner can unlock
- [ ] T-21: server.py — get_status tool — File: `src/server.py` — MCP tool `get_status()` that returns all current locks, connected users info, project root path
- [ ] T-22: server.py — git_status tool — File: `src/server.py` — MCP tool `git_status()` that runs `git status --porcelain` and `git diff --stat` in project_root, returns output as string

### Phase 6 — Tunnel Module
- [ ] T-23: tunnel.py — start_tunnel — File: `src/tunnel.py` — function `start_tunnel(port: int) -> str` that starts a Cloudflare tunnel using cloudflared subprocess, parses and returns the HTTPS URL
- [ ] T-24: tunnel.py — stop_tunnel — File: `src/tunnel.py` — function `stop_tunnel(process)` that gracefully terminates the cloudflared subprocess
- [ ] T-25: test_tunnel.py — File: `tests/test_tunnel.py` — test that start_tunnel returns a URL string starting with https://, test stop_tunnel doesn't raise on valid process (mock subprocess)

### Phase 7 — CLI Commands
- [ ] T-26: cli.py — start command — File: `src/cli.py` — command `letswork start` that: generates token, starts MCP server on a port, starts tunnel, prints URL + token to terminal
- [ ] T-27: cli.py — stop command — File: `src/cli.py` — command `letswork stop` that: stops the tunnel, stops the server, prints confirmation
- [ ] T-28: cli.py — status command — File: `src/cli.py` — command `letswork status` that: prints current locks, connected info, tunnel URL if running

### Phase 8 — Integration & Wiring
- [ ] T-29: server.py — path safety — File: `src/server.py` — function `safe_resolve(path: str, root: str) -> str` that resolves path and ensures it stays inside project_root (prevents directory traversal)
- [ ] T-30: server.py — apply safe_resolve — File: `src/server.py` — update all MCP tools (list_files, read_file, write_file) to use `safe_resolve` before any file operation
- [ ] T-31: cli.py — wire everything — File: `src/cli.py` — update `start` command to properly initialize server with project_root=cwd, pass token, connect tunnel to server port

### Phase 9 — Testing & Polish
- [ ] T-32: test_server.py — File: `tests/test_server.py` — integration tests: list_files returns files, read_file reads content, write_file with lock, write_file rejected when locked by other
- [ ] T-33: README.md final — File: `README.md` — complete documentation: install instructions, quick start for both developers, architecture diagram, requirements
- [ ] T-34: docs/architecture.md — File: `docs/architecture.md` — document decisions already established in spec.md

## Blocked
(nothing currently blocked)

## Backlog
- [ ] B-01: .gitignore — standard Python gitignore
- [ ] B-02: GitHub Actions CI — run tests on push
- [ ] B-03: PyPI publishing setup — build and upload to PyPI
- [ ] B-04: MCP Registry submission — submit to registry.modelcontextprotocol.io
- [ ] B-05: Multi-OS testing — verify file locking on Windows (msvcrt) vs Unix (fcntl)
- [ ] B-06: Rate limiting — prevent abuse on the tunnel endpoint
- [ ] B-07: Session timeout — auto-release locks after inactivity
- [ ] B-08: Reconnection handling — what happens if Developer B disconnects mid-session

---

## Task Dependency Map
T-01 (pyproject.toml)
↓
T-02 (src/init.py)
↓
T-03 (cli.py scaffold) ←──────────────────────────────┐
↓                                                     │
T-05 → T-06 → T-07 (auth module complete)              │
↓                                                     │
T-08 → T-09 → T-10 → T-11 → T-12 → T-13 (locks done) │
↓                                                     │
T-14 → T-15 (server foundation)                        │
↓                                                     │
T-16 → T-17 → T-18 → T-19 → T-20 → T-21 → T-22       │
(all MCP tools)                                       │
↓                                                     │
T-23 → T-24 → T-25 (tunnel module)                     │
↓                                                     │
T-26 → T-27 → T-28 (CLI commands) ─────────────────────┘
↓
T-29 → T-30 → T-31 (integration)
↓
T-32 → T-33 → T-34 (testing & polish)

## Task Size Verification
Every task above follows WORKFLOW.md rules:
- 1 file per task: ✅
- 1 function/class per task: ✅ (except test files which test one module)
- ~30 lines max per task: ✅
- 0 design decisions left to Gemini: ✅
- 0 ambiguous instructions: ✅

---

*Last updated: Session 2 — Task breakdown complete*
