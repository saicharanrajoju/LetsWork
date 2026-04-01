import subprocess
import shutil
import sys


def _open_terminal(command: str, project_root: str) -> bool:
    """
    Open a new terminal window running `command` in `project_root`.
    Returns True if a terminal was launched, False if we fell back to printing.
    """
    if sys.platform == "darwin":
        script = f'''
        tell application "Terminal"
            do script "cd {project_root} && {command}"
        end tell
        '''
        subprocess.Popen(["osascript", "-e", script])
        return True

    if sys.platform.startswith("linux"):
        # Try common Linux terminal emulators in order of preference
        for term, args in [
            ("gnome-terminal", ["--", "bash", "-c", f"cd {project_root} && {command}; exec bash"]),
            ("xfce4-terminal", ["-e", f"bash -c 'cd {project_root} && {command}; exec bash'"]),
            ("konsole", ["--noclose", "-e", "bash", "-c", f"cd {project_root} && {command}"]),
            ("xterm", ["-e", f"bash -c 'cd {project_root} && {command}; exec bash'"]),
        ]:
            if shutil.which(term):
                subprocess.Popen([term] + args)
                return True
        return False

    if sys.platform == "win32":
        # Windows Terminal (wt) or fallback to cmd
        if shutil.which("wt"):
            subprocess.Popen(["wt", "new-tab", "--title", "LetsWork",
                              "cmd", "/k", f"cd /d {project_root} && {command}"])
        else:
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k",
                              f"cd /d {project_root} && {command}"])
        return True

    return False


def _make_banner(mcp_url: str, token: str) -> str:
    """Shell command that prints the LetsWork banner then launches claude."""
    return (
        f"clear && "
        f"echo '╔══════════════════════════════════════════════════╗' && "
        f"echo '║  Claude Code — Connected to LetsWork             ║' && "
        f"echo '║                                                  ║' && "
        f"echo '║  MCP URL: {mcp_url}' && "
        f"echo '║  Token:   {token}' && "
        f"echo '║                                                  ║' && "
        f"echo '║  Try: list_files, read_file, write_file          ║' && "
        f"echo '╚══════════════════════════════════════════════════╝' && "
        f"echo '' && claude"
    )


def launch_claude_code(project_root: str, tunnel_url: str, token: str) -> None:
    """Open a new terminal window with Claude Code for the host."""
    if not shutil.which("claude"):
        print("⚠️  Claude Code not found. Install: npm install -g @anthropic-ai/claude-code")
        return

    mcp_url = f"{tunnel_url}/mcp"
    launched = _open_terminal(_make_banner(mcp_url, token), project_root)
    if not launched:
        print("Open a new terminal, cd to your project, and run: claude")


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
    """Open a new terminal window with Claude Code for the guest."""
    if not shutil.which("claude"):
        print("⚠️  Claude Code not found. Install: npm install -g @anthropic-ai/claude-code")
        return

    launched = _open_terminal(_make_banner(url, token), project_root)
    if not launched:
        print("Open a new terminal, cd to your project, and run: claude")
