import os
import click
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
    import threading
    from letswork.events import EventLog
    from letswork.launcher import launch_with_claude_code

    # Set up project root
    project_root = os.getcwd()
    server_module.project_root = project_root

    # Generate token and register host
    token = generate_token()
    server_module.session_token = token
    server_module.register_user(token, "host")

    # Set up event log
    event_log = EventLog()
    server_module.event_log = event_log

    # Set up approval queue
    from letswork.approval import ApprovalQueue
    approval_queue = ApprovalQueue(project_root)
    server_module.approval_queue = approval_queue

    # Start tunnel
    try:
        url, tunnel_process = start_tunnel(port)
    except RuntimeError as e:
        click.echo(f"Error: {e}")
        return

    # Print session info
    click.echo("")
    click.echo("╔══════════════════════════════════════════════════╗")
    click.echo("║  LetsWork Session Active                        ║")
    click.echo("║                                                 ║")
    click.echo(f"║  URL:   {url}/mcp")
    click.echo(f"║  Token: {token}")
    click.echo("║                                                 ║")
    click.echo("║  Share both with your collaborator.             ║")
    click.echo("╚══════════════════════════════════════════════════╝")
    click.echo("")

    # Suppress uvicorn access logs before server starts
    import logging
    for _log_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi"):
        _l = logging.getLogger(_log_name)
        _l.setLevel(logging.CRITICAL)
        _l.propagate = False
    logging.getLogger("httpx").setLevel(logging.CRITICAL)

    # Start MCP server in a background thread
    def run_server():
        import logging as _logging
        import uvicorn
        # Override uvicorn's log config before any handlers are added
        uvicorn.config.LOGGING_CONFIG["loggers"]["uvicorn.access"]["level"] = "CRITICAL"
        uvicorn.config.LOGGING_CONFIG["loggers"]["uvicorn"]["level"] = "CRITICAL"
        for _log_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi"):
            _l = _logging.getLogger(_log_name)
            _l.setLevel(_logging.CRITICAL)
            _l.propagate = False
        server_module.app.settings.host = "127.0.0.1"
        server_module.app.settings.port = port
        server_module.app.settings.stateless_http = True
        if hasattr(server_module.app.settings, "transport_security") and server_module.app.settings.transport_security:
            server_module.app.settings.transport_security.enable_dns_rebinding_protection = False
        server_module.app.run(transport="streamable-http")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give server a moment to start
    import time
    time.sleep(2)

    # Launch tmux split with TUI + Claude Code
    try:
        launch_with_claude_code(project_root, url, token, port)
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
    if not url.endswith("/mcp"):
        url = url.rstrip("/") + "/mcp"
    from letswork.events import EventLog
    from letswork.filelock import LockManager
    from letswork.tui.app import LetsWorkApp
    from letswork.launcher import launch_guest_claude_code

    click.echo(f"Connecting to {url}...")
    click.echo(f"User: {user}")
    click.echo("")

    # Guest TUI uses a local event log for display
    event_log = EventLog()
    lock_manager = LockManager()
    
    # Guest doesn't have local project root — use a temp dir
    # Files are accessed remotely through MCP tools
    project_root = os.getcwd()

    launch_guest_claude_code(url, token)

    app = LetsWorkApp(
        project_root=project_root,
        lock_manager=lock_manager,
        event_log=event_log,
        approval_queue=None,
        guest_mode=True,
        mcp_url=url,
        mcp_token=token,
        user_id=user,
    )
    app.run()


@cli.command()
def stop():
    click.echo("In v1, use Ctrl+C in the terminal running 'letswork start' to stop the session.")


@cli.command()
def status():
    click.echo("In v1, use the get_status MCP tool to check session status.")
    click.echo("A standalone status command will be available in v2.")


if __name__ == "__main__":
    cli()
