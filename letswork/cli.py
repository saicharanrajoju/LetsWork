import os
import time
import click
import threading
import logging
import letswork.server as server_module
from letswork.auth import generate_token
from letswork.tunnel import start_tunnel, stop_tunnel


@click.group()
def cli():
    """LetsWork — real-time collaborative coding via MCP."""
    pass


@cli.command()
@click.option("--port", default=8000, type=int, help="Port for the MCP server")
def start(port):
    """Start a LetsWork collaboration session."""
    from letswork.events import EventLog
    from letswork.approval import ApprovalQueue
    from letswork.launcher import launch_claude_code

    project_root = os.getcwd()
    server_module.project_root = project_root

    token = generate_token()
    server_module.session_token = token
    server_module.register_user(token, "host")

    server_module.event_log = EventLog()
    server_module.approval_queue = ApprovalQueue(project_root)

    # Start tunnel
    try:
        url, tunnel_process = start_tunnel(port)
    except RuntimeError as e:
        click.echo(f"Error: {e}")
        return

    mcp_url = f"{url}/mcp"

    # Suppress all server/framework logs
    for _name in ("uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi",
                  "httpx", "mcp", "mcp.server", "asyncio"):
        _l = logging.getLogger(_name)
        _l.setLevel(logging.CRITICAL)
        _l.propagate = False
    logging.root.setLevel(logging.CRITICAL)

    # Start MCP server in background thread
    def run_server():
        import uvicorn.config as _uvc
        _uvc.LOGGING_CONFIG = {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {"null": {"class": "logging.NullHandler"}},
            "loggers": {
                "uvicorn":        {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
                "uvicorn.error":  {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
                "uvicorn.access": {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
            },
        }
        server_module.app.settings.host = "127.0.0.1"
        server_module.app.settings.port = port
        server_module.app.settings.stateless_http = True
        if hasattr(server_module.app.settings, "transport_security") and server_module.app.settings.transport_security:
            server_module.app.settings.transport_security.enable_dns_rebinding_protection = False
        server_module.app.run(transport="streamable-http")

    threading.Thread(target=run_server, daemon=True).start()
    time.sleep(2)

    # Open Claude Code in a new Terminal window
    launch_claude_code(project_root, url, token)

    # Print session info and keep server alive
    click.echo("")
    click.echo("╔══════════════════════════════════════════════════╗")
    click.echo("║  🤖 LetsWork Session Active                      ║")
    click.echo("║                                                  ║")
    click.echo(f"║  MCP URL: {mcp_url}")
    click.echo(f"║  Token:   {token}")
    click.echo("║                                                  ║")
    click.echo("║  Share the URL + Token with your collaborator.   ║")
    click.echo("║  Press Ctrl+C to stop the session.               ║")
    click.echo("╚══════════════════════════════════════════════════╝")
    click.echo("")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
    finally:
        stop_tunnel(tunnel_process)
        click.echo("Session ended.")


@cli.command()
@click.argument("url")
@click.option("--token", prompt="Enter session token", help="Secret token from the host")
@click.option("--user", default="guest", help="Your username")
def join(url, token, user):
    """Join a LetsWork session as a guest."""
    from letswork.launcher import register_guest_mcp, launch_guest_claude_code

    if not url.endswith("/mcp"):
        url = url.rstrip("/") + "/mcp"

    click.echo(f"\nConnecting to {url} as {user}...")

    # Register MCP with Claude Code (via stdio proxy — reliable over Cloudflare)
    register_guest_mcp(url, token)

    # Open Claude Code in a new Terminal window (banner shows token for reference)
    launch_guest_claude_code(os.getcwd(), url, token)

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
