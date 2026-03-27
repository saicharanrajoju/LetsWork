<!-- mcp-name: io.github.saicharanrajoju/letswork -->

# LetsWork

**Google Docs for AI-assisted coding** — real-time collaboration on a local codebase using two independent Claude subscriptions.

## What is LetsWork?

LetsWork is an MCP (Model Context Protocol) server that lets two developers work on the same local codebase simultaneously, each using their own Claude. One developer hosts, the other connects — with file-level locking to prevent conflicts.

## How It Works

1. Developer A (Host) runs `letswork start` in their project folder
2. A secure HTTPS tunnel is created automatically via Cloudflare
3. A one-time URL + secret token is generated
4. Developer A shares both with Developer B (Guest)
5. Developer B connects: `claude mcp add letswork --transport http <url>`
6. Both can now read, write, and list files — with lock protection

## Quick Start

### Install
```bash
pip install letswork
```

### Requirements

- Python >= 3.10
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) installed and available in PATH
- Git (recommended for conflict safety)

### Host (Developer A)
```bash
cd /path/to/your/project
letswork start
```

You'll see:
╔══════════════════════════════════════════════════╗
║  LetsWork Session Active                        ║
║                                                 ║
║  URL:   https://abc123.trycloudflare.com        ║
║  Token: a1b2c3d4e5f6...                         ║
║                                                 ║
║  Share both with your collaborator.             ║
║  Press Ctrl+C to end session.                   ║
╚══════════════════════════════════════════════════╝

Share the URL and token with your collaborator via Slack, Discord, or text.

### Guest (Developer B)
```bash
claude mcp add letswork --transport http <URL_FROM_HOST>
```

Use the token when prompted. You now have full access to the shared codebase through your own Claude.

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `list_files` | List files and directories with lock status |
| `read_file` | Read file contents (1MB limit) |
| `write_file` | Write to a file (requires lock) |
| `lock_file` | Lock a file for exclusive editing |
| `unlock_file` | Release a file lock |
| `get_status` | Show session info and active locks |
| `send_message` | Send a chat message to the other developer |
| `get_events` | Get activity events since a given index |
| `get_pending_changes` | View changes awaiting host approval |
| `approve_change` | Approve a pending change (host only) |
| `reject_change` | Reject a pending change (host only) |

## Security

- Unguessable tunnel URL (random Cloudflare subdomain)
- Cryptographic secret token (second auth layer)
- All traffic encrypted via HTTPS
- Path traversal prevention (no access outside project root)
- No accounts, no signup, no persistent credentials

## CLI Commands

| Command | Description |
|---------|-------------|
| `letswork start [--port PORT]` | Start session (default port: 8000) |
| `letswork stop` | Stop instructions (use Ctrl+C in v1) |
| `letswork status` | Status instructions (use get_status tool in v1) |

## Architecture
Developer A's Machine:
[Local Codebase] ← [MCP Server] ← [Cloudflare Tunnel] ← HTTPS URL
↑
Developer B connects here
with secret token

## Constraints (v1)

- Maximum 2 users per session (Host + Guest)
- Text files only (no binary support)
- 1MB file size limit per operation
- File operations only (no shell access for Guest)

## License

MIT

---

Built with the [Model Context Protocol](https://modelcontextprotocol.io).
