# LetsWork — Architecture Decisions

*Record of every architectural decision made during development.
Read this at the start of every session to avoid contradicting past decisions.*

---

## Decision: Python as Implementation Language
Date: Session 1
Decision: Use Python for the entire project
Reasoning: The official Anthropic MCP SDK is Python-first with the best documentation and examples. The target audience (developers using Claude) overwhelmingly uses Python. Click provides excellent CLI tooling in Python.
Alternatives rejected: TypeScript (MCP SDK exists but Python SDK is more mature), Rust (no official MCP SDK), Go (no official MCP SDK)
Impact: All source files are .py, packaging via PyPI, dependencies are Python packages

## Decision: FastMCP as Server Framework
Date: Session 1
Decision: Use FastMCP from the official mcp Python SDK
Reasoning: FastMCP is the high-level API provided by Anthropic's own MCP SDK. It handles protocol details, tool registration, and transport layers. Using the official SDK ensures compatibility with Claude Code and other MCP clients.
Alternatives rejected: Building raw MCP protocol handling manually (unnecessary complexity), third-party MCP libraries (less maintained than official SDK)
Impact: Server defined in src/server.py using @app.tool() decorators, transport handled by FastMCP

## Decision: Cloudflare Tunnel for Networking
Date: Session 1
Decision: Use cloudflared (Cloudflare Tunnel) to expose the local MCP server
Reasoning: Free tier sufficient, no port forwarding needed, no VPN needed, no DNS configuration, works behind NATs and firewalls, HTTPS by default. The tunnel creates a random subdomain on trycloudflare.com.
Alternatives rejected: ngrok (requires account, has rate limits on free tier), localtunnel (less reliable), direct port forwarding (requires router config, not user-friendly), Tailscale (requires both users to install and configure)
Impact: cloudflared is an external dependency that must be pre-installed. src/tunnel.py manages the subprocess lifecycle.

## Decision: In-Memory File Locking
Date: Session 1
Decision: Use a Python dictionary for file lock tracking (path -> user_id)
Reasoning: Simple, fast, no external dependencies. Locks only need to persist for the duration of a session. When the session ends, all locks are released automatically since the process exits.
Alternatives rejected: File-system level locks with fcntl/msvcrt (cross-platform complexity, doesn't track user identity), Redis (overkill external dependency), SQLite (unnecessary persistence)
Impact: LockManager class in src/filelock.py with a dict. Locks are lost if the process crashes — acceptable for v1 since Git is the safety net.

## Decision: Secret Token Authentication
Date: Session 1
Decision: Generate a cryptographic random token per session using secrets.token_urlsafe
Reasoning: Simple, no accounts needed, no persistent credentials. Combined with the unguessable tunnel URL, this provides two layers of security. Token is shared out-of-band (Slack, Discord, text).
Alternatives rejected: OAuth (massive complexity for a CLI tool), API keys (requires persistent storage), mutual TLS (complex setup for end users)
Impact: src/auth.py generates and validates tokens. Token is set once at session start and checked on every request.

## Decision: Centralized Path Safety via safe_resolve
Date: Session 4
Decision: Create a single safe_resolve(path) function used by all MCP tools for path resolution and traversal prevention
Reasoning: Initially each tool had inline path resolution logic (os.path.join, os.path.abspath, startswith check). This was duplicated across 5 tools. Extracting it into safe_resolve eliminates duplication and ensures a single point of security enforcement.
Alternatives rejected: Keeping inline checks per tool (duplication, risk of inconsistency), middleware-level path check (FastMCP doesn't natively support pre-tool middleware)
Impact: All tools call safe_resolve(path) first. Any path outside project_root raises ValueError.

## Decision: Click for CLI Framework
Date: Session 1
Decision: Use Click for the command-line interface
Reasoning: Click is the standard Python CLI library — well-documented, widely used, supports groups, commands, options, and help text out of the box. Minimal code for a professional CLI.
Alternatives rejected: argparse (more verbose, less elegant), Typer (adds a dependency on top of Click), fire (too magic, less control)
Impact: src/cli.py defines a Click group with start, stop, and status commands

## Decision: Streamable HTTP Transport
Date: Session 4
Decision: Run the MCP server with transport="streamable-http"
Reasoning: This is the transport mode required for remote MCP connections over HTTPS tunnels. The Guest connects via HTTP to the Cloudflare tunnel URL, which forwards to the local server.
Alternatives rejected: stdio transport (only works for local connections, not over network), SSE transport (older protocol, streamable-http is the current standard)
Impact: app.run() in cli.py uses transport="streamable-http" with host="127.0.0.1"

## Decision: v1 Scope Boundaries
Date: Session 1
Decision: Limit v1 to exactly 2 users, text files only, 1MB limit, no directory creation/deletion, no shell access for Guest
Reasoning: Shipping a focused, working tool is more important than feature completeness. Every constraint can be relaxed in v2 based on real user feedback. The core value proposition (two developers, one codebase, real-time) works within these constraints.
Alternatives rejected: Building multi-user support from the start (complexity), supporting binary files (encoding complexity), adding shell access (security risk)
Impact: All tools enforce these limits. Future scope documented in spec.md Section 9.

---

*Last updated: Session 5 — All architecture decisions documented*
