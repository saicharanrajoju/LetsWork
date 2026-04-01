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
def start(port):
    """Start a LetsWork collaboration session."""
    from letswork.events import EventLog
    from letswork.approval import ApprovalQueue
    from letswork.launcher import launch_claude_code, register_guest_mcp

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

    # Silence MCP and uvicorn loggers before server starts
    import logging
    for _name in ("uvicorn", "uvicorn.access", "uvicorn.error", "mcp", "mcp.server",
                  "mcp.server.streamable_http", "asyncio"):
        logging.getLogger(_name).setLevel(logging.CRITICAL)

    # Disable DNS rebinding protection so Cloudflare tunnel host header is accepted
    if (hasattr(server_module.app.settings, "transport_security")
            and server_module.app.settings.transport_security):
        server_module.app.settings.transport_security.enable_dns_rebinding_protection = False

    # Start MCP server in background thread — run uvicorn directly so we can
    # pass log_config=None, which fully disables all uvicorn request logging.
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

    # Wait until the server is actually responding (any HTTP response means it's up)
    import urllib.request
    import urllib.error
    for _ in range(20):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/mcp", timeout=1)
        except urllib.error.HTTPError:
            break  # Got an HTTP response — server is up
        except Exception:
            time.sleep(0.5)

    # Register letswork MCP for the host too (needed for approvals)
    register_guest_mcp(mcp_url, token)

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
