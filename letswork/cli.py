import os
import time
import click
import threading
import letswork.server as server_module
from letswork.auth import generate_token
from letswork.tunnel import start_tunnel, stop_tunnel


@click.group()
def cli():
    """LetsWork — real-time collaborative coding via MCP."""
    pass


@cli.command()
@click.option("--port", default=8000, type=int, help="Port for the MCP server")
@click.option("--debug", is_flag=True, help="Show live tool call activity")
def start(port, debug):
    """Start a LetsWork collaboration session."""
    import logging
    from letswork.events import EventLog, EventType
    from letswork.approval import ApprovalQueue
    from letswork.launcher import launch_claude_code, register_guest_mcp

    project_root = os.getcwd()
    server_module.project_root = project_root

    host_token = generate_token()
    guest_token = generate_token()
    server_module.register_user(host_token, "host")
    server_module.register_user(guest_token, "guest")

    event_log = EventLog()
    server_module.event_log = event_log
    approval_queue = ApprovalQueue(project_root)
    server_module.approval_queue = approval_queue

    def _on_approved(change):
        event_log.emit(EventType.FILE_WRITE, change.user_id,
                       {"path": change.path, "status": "approved"})

    def _on_rejected(change):
        event_log.emit(EventType.FILE_WRITE, change.user_id,
                       {"path": change.path, "status": "rejected"})

    approval_queue.on_approved(_on_approved)
    approval_queue.on_rejected(_on_rejected)

    # Start tunnel
    try:
        url, tunnel_process = start_tunnel(port)
    except RuntimeError as e:
        click.echo(f"[ERROR] Tunnel failed: {e}")
        return

    mcp_url = f"{url}/mcp"

    # Silence MCP and uvicorn loggers
    for _name in ("uvicorn", "uvicorn.access", "uvicorn.error", "mcp", "mcp.server",
                  "mcp.server.streamable_http", "asyncio"):
        logging.getLogger(_name).setLevel(logging.CRITICAL)

    # Disable DNS rebinding protection so Cloudflare tunnel host header is accepted
    if (hasattr(server_module.app.settings, "transport_security")
            and server_module.app.settings.transport_security):
        server_module.app.settings.transport_security.enable_dns_rebinding_protection = False

    # Start MCP server in background thread
    def run_server():
        import anyio
        import uvicorn

        async def _serve():
            starlette_app = server_module.app.streamable_http_app()
            config = uvicorn.Config(
                starlette_app,
                host="127.0.0.1",
                port=port,
                log_config=None,
                log_level="critical",
            )
            await uvicorn.Server(config).serve()

        anyio.run(_serve)

    threading.Thread(target=run_server, daemon=True).start()

    # Wait until server is up
    import urllib.request
    import urllib.error
    click.echo("[letswork] Starting MCP server...", err=True)
    for _ in range(20):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/mcp", timeout=1)
        except urllib.error.HTTPError:
            break  # Got an HTTP response — server is up
        except Exception:
            time.sleep(0.5)
    else:
        click.echo("[ERROR] MCP server did not start in time. Try again.", err=True)
        stop_tunnel(tunnel_process)
        return

    click.echo(f"[letswork] MCP server running on port {port}", err=True)

    # Background thread: expire stale locks every 60 seconds
    def _lock_cleanup():
        while True:
            time.sleep(60)
            expired = server_module.lock_manager.release_expired(max_age_seconds=1800)
            for path in expired:
                event_log.emit(EventType.FILE_UNLOCK, "system", {"path": path, "expired": True})

    threading.Thread(target=_lock_cleanup, daemon=True).start()

    # Write CLAUDE.md into the project root so Claude Code knows about letswork tools
    claude_md_path = os.path.join(project_root, "CLAUDE.md")
    _created_claude_md = not os.path.exists(claude_md_path)
    if _created_claude_md:
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(
                "# LetsWork Session Active\n\n"
                "A guest is connected and collaborating on this project via MCP.\n\n"
                "Use these MCP tools to manage the collaboration:\n"
                "- `get_notifications` — check pending changes and active locks\n"
                "- `get_pending_changes` — review guest edits with diffs\n"
                "- `approve_change` — approve and write a guest's change to disk\n"
                "- `reject_change` — reject a guest's change\n"
                "- `force_unlock` — release a stuck file lock (host only)\n"
                "- `get_status` — see connected users and session info\n"
            )

    # Register letswork MCP for the host (needed for approvals)
    click.echo("[letswork] Registering host MCP...", err=True)
    register_guest_mcp(mcp_url, host_token)

    # Open Claude Code in a new Terminal window
    launch_claude_code(project_root, url)

    join_cmd = f"letswork join {url} --token {guest_token}"

    # Print session info
    click.echo("")
    click.echo("╔══════════════════════════════════════════════════════════════════════╗")
    click.echo("║  🤝 LetsWork Session Active                                          ║")
    click.echo("║                                                                      ║")
    click.echo("║  Send this command to your collaborator:                             ║")
    click.echo(f"║  {join_cmd}")
    click.echo("║                                                                      ║")
    click.echo("║  Press Ctrl+C to stop.                                               ║")
    click.echo("╚══════════════════════════════════════════════════════════════════════╝")
    click.echo("")
    click.echo("── Notifications ───────────────────────────────────────────────────────")
    click.echo("")

    # Always-on notifications — important events only
    def _notify(event):
        ts = event.timestamp.strftime("%H:%M:%S")
        if event.event_type == EventType.FILE_WRITE:
            status = event.data.get("status")
            path = event.data.get("path", "?")
            change_id = event.data.get("change_id", "")
            user = event.user_id
            if status == "pending_approval":
                click.echo(f"  [{ts}] 📝 {user} submitted change to {path} (ID: {change_id})")
                click.echo(f"         → run: get_pending_changes in Claude Code to review")
            elif status == "approved":
                click.echo(f"  [{ts}] ✅ Change to {path} approved and written to disk")
            elif status == "rejected":
                click.echo(f"  [{ts}] ❌ Change to {path} rejected")
            else:
                click.echo(f"  [{ts}] ✏️  {user} wrote {path}")
        elif event.event_type == EventType.CONNECTION:
            click.echo(f"  [{ts}] 🔌 {event.user_id} connected")
        elif event.event_type == EventType.ERROR:
            click.echo(f"  [{ts}] ⚠️  {event.data.get('error', '?')}")
        elif event.event_type == EventType.PING:
            click.echo(f"  [{ts}] 🏓 {event.user_id} pinged")
        if debug:
            if event.event_type not in (
                EventType.FILE_WRITE, EventType.CONNECTION,
                EventType.ERROR, EventType.PING,
            ):
                click.echo(f"  [{ts}] [debug] {event.event_type.value} — {event.data}")

    event_log.on_event(_notify)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\n[letswork] Shutting down...")
    finally:
        stop_tunnel(tunnel_process)
        if _created_claude_md and os.path.exists(claude_md_path):
            os.remove(claude_md_path)
        click.echo("[letswork] Session ended.")


@cli.command()
@click.argument("url")
@click.option("--token", prompt="Enter session token", help="Guest token from the host")
def join(url, token):
    """Join a LetsWork session as a guest."""
    from letswork.launcher import register_guest_mcp, launch_guest_claude_code

    if not url.endswith("/mcp"):
        mcp_url = url.rstrip("/") + "/mcp"
    else:
        mcp_url = url

    click.echo(f"\n[letswork] Connecting to {mcp_url}...")

    # Register MCP with Claude Code (via stdio proxy)
    register_guest_mcp(mcp_url, token)

    # Open Claude Code in a new Terminal window
    launch_guest_claude_code(mcp_url)

    click.echo("✅ Claude Code is opening with LetsWork MCP connected.")
    click.echo("   You can close this terminal.")


@cli.command()
def stop():
    click.echo("Use Ctrl+C in the terminal running 'letswork start' to stop.")


@cli.command()
def status():
    click.echo("Use the get_status MCP tool inside Claude Code to check session status.")


if __name__ == "__main__":
    cli()
