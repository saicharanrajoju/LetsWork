# LetsWork — Product Specification
*Version 1.0 — Source of truth for what LetsWork does and how.*

---

## 1. Product Summary

LetsWork is an MCP (Model Context Protocol) server that enables 
two developers to collaborate on the same local codebase in 
real time, each using their own Claude subscription independently.

One developer (the Host) runs LetsWork in their project folder. 
It starts an MCP server, creates a secure Cloudflare tunnel, 
and generates a one-time URL + secret token. A second developer 
(the Guest) adds that URL as an MCP server in their Claude Code. 
Both can now read and write files in the same codebase with 
file-level locking to prevent conflicts.

---

## 2. Users

### Host (Developer A)
- Has the codebase on their local machine
- Runs `letswork start` to begin a session
- Shares the generated URL + token with the Guest
- Can read, write, list, and lock files
- Can see which files the Guest has locked
- Can end the session at any time

### Guest (Developer B)
- Does NOT have the codebase locally
- Receives the URL + token from the Host
- Connects via `claude mcp add letswork --transport http <url>`
- Can read, write, list, and lock files
- Can see which files the Host has locked
- Connection ends when the Host stops the session

---

## 3. Core Features

### 3.1 Session Management
- Host runs `letswork start` in any project directory
- A local MCP server starts on a random available port
- A Cloudflare tunnel is created automatically (no config needed)
- A unique session URL (HTTPS) is generated
- A one-time secret token is generated for authentication
- Host sees: URL, token, and session status in terminal
- Session ends when Host runs `letswork stop` or Ctrl+C

### 3.2 File Operations (MCP Tools)
LetsWork exposes these MCP tools to both Host and Guest Claude:

| Tool Name       | Parameters              | Description                         |
|-----------------|-------------------------|-------------------------------------|
| `read_file`     | `path: str`             | Read contents of a file             |
| `write_file`    | `path: str, content: str` | Write content to a file           |
| `list_files`    | `path: str` (optional)  | List files in directory (default: root) |
| `lock_file`     | `path: str`             | Lock a file for exclusive editing   |
| `unlock_file`   | `path: str`             | Release lock on a file              |
| `get_locks`     | (none)                  | Show all currently locked files     |
| `get_status`    | (none)                  | Show session info and connected users |

### 3.3 File Locking
- Before writing, a developer must lock the file
- Only one developer can lock a file at a time
- Attempting to lock an already-locked file returns an error 
  with the name of the holder
- Locks are released explicitly via `unlock_file` or 
  automatically when the session ends
- `get_locks` shows all active locks with holder identity
- `write_file` automatically checks lock ownership before writing

### 3.4 Authentication
- On session start, a random secret token is generated 
  (cryptographically secure, 32 characters)
- Every request from the Guest must include this token
- Invalid tokens are rejected with 401 Unauthorized
- Token is single-use per session (new token each `letswork start`)
- No accounts, no signup, no persistent credentials

### 3.5 Tunneling
- Cloudflare Tunnel (via `cloudflared`) creates a public 
  HTTPS URL for the local MCP server
- No port forwarding required
- No VPN required
- No DNS configuration required
- Works behind NATs and firewalls
- Free tier is sufficient
- If `cloudflared` is not installed, LetsWork prints 
  clear installation instructions and exits

---

## 4. CLI Interface

### Commands:
```
letswork start [--port PORT]
```
- Starts MCP server + tunnel in current directory
- Optional: specify port (default: auto-select available port)
- Outputs: session URL, secret token, status
```
letswork stop
```
- Stops the MCP server and closes the tunnel
- Releases all file locks
- Ends the session cleanly
```
letswork status
```
- Shows: running/stopped, connected users, active locks, 
  session duration, tunnel URL

### Terminal Output on Start:
```
╔══════════════════════════════════════════════════╗
║  LetsWork Session Active                        ║
║                                                 ║
║  URL:   https://abc123.trycloudflare.com        ║
║  Token: a1b2c3d4e5f6...                         ║
║                                                 ║
║  Share both with your collaborator.              ║
║  Press Ctrl+C to end session.                   ║
╚══════════════════════════════════════════════════╝
```

---

## 5. Security Model

### Threat Model:
- The tunnel URL is unguessable (random subdomain from Cloudflare)
- The secret token adds a second layer of authentication
- Both are required — URL alone is not enough
- Token is transmitted out-of-band (Host sends it via 
  Slack/Discord/text, not through the tunnel itself)
- All traffic is encrypted via HTTPS (Cloudflare handles TLS)

### What LetsWork does NOT protect against:
- A malicious Guest who has the valid token 
  (they have full read/write access by design)
- Network-level attacks on Cloudflare's infrastructure
- Files outside the project directory 
  (LetsWork restricts paths to project root — see Section 6)

### Path Traversal Prevention:
- All file paths are resolved relative to the project root
- Any path containing `..` or resolving outside the project 
  directory is rejected with 403 Forbidden
- Symlinks pointing outside the project directory are rejected

---

## 6. Constraints & Boundaries

### What LetsWork IS:
- A real-time file collaboration tool for two developers
- An MCP server that any MCP-compatible client can connect to
- A lightweight CLI tool with zero configuration

### What LetsWork is NOT:
- Not a version control system (use Git for that)
- Not a code editor or IDE
- Not a cloud storage service
- Not a deployment tool
- Not a multi-tenant platform (one Host, one Guest per session)

### Technical Constraints:
- Maximum 2 concurrent users per session (Host + Guest)
- File operations only (no terminal/shell access for Guest)
- No directory creation/deletion via MCP tools 
  (only file read/write/list)
- No binary file support in v1 (text files only)
- Maximum file size: 1MB per read/write operation
- Project root is the directory where `letswork start` was run

---

## 7. Dependencies

| Dependency       | Purpose                    | Required? |
|------------------|----------------------------|-----------|
| Python >= 3.10   | Runtime                    | Yes       |
| mcp SDK          | MCP server implementation  | Yes       |
| cloudflared      | Tunnel creation            | Yes (external) |
| click            | CLI framework              | Yes       |
| secrets (stdlib) | Token generation           | Yes (built-in) |
| fcntl / msvcrt   | File locking               | Yes (built-in) |
| pathlib (stdlib) | Path resolution & safety   | Yes (built-in) |
| git              | Conflict safety net        | Recommended |

---

## 8. Error Handling Summary

| Situation                        | Behavior                              |
|----------------------------------|---------------------------------------|
| `cloudflared` not installed      | Print install instructions, exit      |
| Port already in use              | Auto-select next available port       |
| Invalid token from Guest         | Reject with 401 Unauthorized          |
| File not found on read           | Return clear error message            |
| Path traversal attempt           | Reject with 403 Forbidden             |
| File locked by other user        | Return error with lock holder info    |
| Write without holding lock       | Reject with error                     |
| Tunnel connection drops          | Attempt reconnect, notify Host        |
| Host stops session               | All locks released, Guest disconnected|
| File exceeds 1MB                 | Reject with size limit error          |

---

## 9. Future Scope (v2+, Not for Current Build)

These are explicitly NOT part of v1. Listed here only to 
acknowledge them and prevent scope creep:

- Multi-guest support (3+ developers)
- Directory creation/deletion tools
- Binary file support
- Built-in diff/merge viewer
- Chat between Host and Guest
- Persistent sessions (survive restarts)
- Web UI dashboard
- Access control per file/directory
- Audit log of all operations

---

## 10. Success Criteria for v1

LetsWork v1 is complete when:
1. `pip install letswork` works
2. `letswork start` creates a working MCP server + tunnel
3. A second developer can connect via the URL + token
4. Both can read, write, list files through their Claude
5. File locking prevents simultaneous edits
6. Path traversal is blocked
7. Session starts and stops cleanly
8. Published on PyPI
9. Listed on the official MCP Registry

---

*Last updated: Session 2 — Full specification written*
