import subprocess
import shutil
import sys


def launch_claude_code(project_root: str, tunnel_url: str, token: str) -> None:
    """Open a new Terminal window with Claude Code configured for LetsWork."""
    if sys.platform != "darwin":
        print("Open a new terminal and run: claude")
        return

    claude_path = shutil.which("claude")
    if not claude_path:
        print("⚠️  Claude Code not found. Install with: npm install -g @anthropic-ai/claude-code")
        return

    banner = (
        f"clear && echo '╔══════════════════════════════════════════════════╗' && "
        f"echo '║  🤖 Claude Code — Connected to LetsWork          ║' && "
        f"echo '║                                                  ║' && "
        f"echo '║  MCP URL: {tunnel_url}/mcp' && "
        f"echo '║  Token: {token}' && "
        f"echo '║                                                  ║' && "
        f"echo '║  Try: list_files, read_file, write_file           ║' && "
        f"echo '╚══════════════════════════════════════════════════╝' && "
        f"echo '' && claude"
    )
    script = f'''
    tell application "Terminal"
        do script "cd {project_root} && {banner}"
    end tell
    '''
    subprocess.Popen(["osascript", "-e", script])


def register_guest_mcp(url: str) -> None:
    """Register the LetsWork MCP server with the guest's Claude Code."""
    import threading

    def _configure():
        subprocess.run(
            ["claude", "mcp", "add", "letswork", "--transport", "http", url],
            check=False, capture_output=True, text=True,
        )

    threading.Thread(target=_configure, daemon=True).start()


def launch_guest_claude_code(project_root: str, url: str, token: str) -> None:
    """Open a new Terminal window with Claude Code for the guest."""
    if sys.platform != "darwin":
        print("Open a new terminal and run: claude")
        return

    claude_path = shutil.which("claude")
    if not claude_path:
        print("⚠️  Claude Code not found. Install with: npm install -g @anthropic-ai/claude-code")
        return

    banner = (
        f"clear && echo '╔══════════════════════════════════════════════════╗' && "
        f"echo '║  🤖 Claude Code — Connected to LetsWork          ║' && "
        f"echo '║                                                  ║' && "
        f"echo '║  MCP URL: {url}' && "
        f"echo '║  Token: {token}' && "
        f"echo '║                                                  ║' && "
        f"echo '║  Try: list_files, read_file, write_file           ║' && "
        f"echo '╚══════════════════════════════════════════════════╝' && "
        f"echo '' && claude"
    )
    script = f'''
    tell application "Terminal"
        do script "cd {project_root} && {banner}"
    end tell
    '''
    subprocess.Popen(["osascript", "-e", script])
