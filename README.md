<!-- mcp-name: io.github.saicharanrajoju/letswork -->

# LetsWork

**Google Docs for AI-assisted coding** — real-time collaboration on a local codebase using two independent Claude subscriptions.

## What is LetsWork?

LetsWork is an MCP (Model Context Protocol) server that lets two developers work on the same local codebase simultaneously, each using their own Claude. One developer hosts, the other connects — with file-level locking and an approval system to prevent conflicts.

## How It Works

1. Developer A (Host) runs `letswork start` in their project folder
2. A secure HTTPS tunnel is created automatically via Cloudflare
3. A one-time URL + guest token is generated
4. Developer A shares the join command with Developer B (Guest)
5. Developer B runs `letswork join <url> --token <token>` on their machine
6. Both can now read, write, and list files — with lock protection and approval flow

## Quick Start

### Install

```bash
pip install letswork
```

### Requirements

- Python >= 3.10
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) installed and available in PATH
  - macOS: `brew install cloudflared`
  - Linux: see [Cloudflare docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
  - Windows: use WSL (Ubuntu) and follow Linux instructions
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

### Host (Developer A)

```bash
cd /path/to/your/project
letswork start
```

You'll see a session box with a join command — share it with your collaborator:

```
╔══════════════════════════════════════════════════════════════════════╗
║  🤝 LetsWork Session Active                                          ║
║                                                                      ║
║  Send this command to your collaborator:                             ║
║  letswork join https://abc123.trycloudflare.com --token a1b2c3d4    ║
║                                                                      ║
║  Press Ctrl+C to stop.                                               ║
╚══════════════════════════════════════════════════════════════════════╝
```

Claude Code opens automatically in a new terminal window, already connected to LetsWork.

### Guest (Developer B)

```bash
letswork join <URL_FROM_HOST> --token <TOKEN_FROM_HOST>
```

Claude Code launches automatically with LetsWork MCP connected. No extra steps needed.

> **Windows users:** Run this inside Ubuntu (WSL). Claude Code will launch directly in the same terminal.

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `list_files` | List files and directories with lock status |
| `read_file` | Read file contents (1MB limit) |
| `write_file` | Submit a file change (requires host approval) |
| `lock_file` | Lock a file for exclusive editing |
| `unlock_file` | Release a file lock |
| `get_status` | Show session info, connected users, and active locks |
| `get_notifications` | Quick summary of what needs attention right now |
| `get_pending_changes` | View all changes awaiting host approval with diffs |
| `my_pending_changes` | View your own submitted changes (guest) |
| `approve_change` | Approve a pending change and write it to disk (host only) |
| `reject_change` | Reject a pending change (host only) |
| `force_unlock` | Force-release a stuck file lock (host only) |
| `set_display_name` | Set your display name for the session (guest only) |
| `ping` | Verify connection to the host MCP server |

## Approval Flow

Guest file writes go through an approval queue — they are not written directly to disk:

1. Guest asks Claude to edit a file → `write_file` submits the change
2. Host sees a notification: `📝 guest submitted change to server.py (ID: a1b2c3)`
3. Host asks Claude to review: `get_pending_changes`
4. Host approves or rejects: `approve_change a1b2c3` / `reject_change a1b2c3`

## Security

- Unguessable tunnel URL (random Cloudflare subdomain)
- Cryptographic secret token (second auth layer)
- All traffic encrypted via HTTPS
- Path traversal prevention (no access outside project root)
- File lock timeout — locks auto-expire after 30 minutes
- No accounts, no signup, no persistent credentials

## CLI Commands

| Command | Description |
|---------|-------------|
| `letswork start [--port PORT] [--debug]` | Start a session (default port: 8000) |
| `letswork join <URL> --token <TOKEN>` | Join a session as guest |
| `letswork stop` | Stop instructions (use Ctrl+C in the start terminal) |
| `letswork status` | Status instructions (use `get_status` tool in Claude Code) |

## Architecture

```
Developer A's Machine:
[Local Codebase] ← [MCP Server :8000] ← [Cloudflare Tunnel] ← HTTPS URL
                                                                     ↑
                                              Developer B connects here
                                              via stdio proxy + secret token
```

The guest connects through a stdio proxy (`letswork-proxy`) rather than directly over HTTP — this avoids Cloudflare SSE reliability issues and gives stable MCP connectivity.

## Constraints

- Maximum 2 users per session (Host + Guest)
- Text files only (binary files not supported)
- 1MB file size limit per operation
- File operations only (no shell access for Guest)
- Requires cloudflared on the host machine

## License

MIT

---

Built with the [Model Context Protocol](https://modelcontextprotocol.io).
