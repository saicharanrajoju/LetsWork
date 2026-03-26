import os
import click
import src.server as server_module
from src.auth import generate_token
from src.tunnel import start_tunnel, stop_tunnel


@click.group()
def cli():
    """LetsWork — real-time collaborative coding via MCP."""
    pass


@cli.command()
@click.option("--port", default=8000, type=int, help="Port for the MCP server")
def start(port):
    server_module.project_root = os.getcwd()
    token = generate_token()
    server_module.session_token = token
    url, tunnel_process = start_tunnel(port)
    
    click.echo("")
    click.echo("╔══════════════════════════════════════════════════╗")
    click.echo("║  LetsWork Session Active                        ║")
    click.echo("║                                                 ║")
    click.echo(f"║  URL:   {url}  ║")
    click.echo(f"║  Token: {token}  ║")
    click.echo("║                                                 ║")
    click.echo("║  Share both with your collaborator.             ║")
    click.echo("║  Press Ctrl+C to end session.                   ║")
    click.echo("╚══════════════════════════════════════════════════╝")
    click.echo("")
    
    try:
        server_module.app.run(transport="streamable-http", host="127.0.0.1", port=port)
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
    finally:
        stop_tunnel(tunnel_process)
        click.echo("Session ended.")


@cli.command()
def stop():
    click.echo("In v1, use Ctrl+C in the terminal running 'letswork start' to stop the session.")


@cli.command()
def status():
    click.echo("In v1, use the get_status MCP tool to check session status.")
    click.echo("A standalone status command will be available in v2.")


if __name__ == "__main__":
    cli()
