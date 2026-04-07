import os
import shlex
import shutil
import subprocess
import sys
import tempfile


def _is_wsl() -> bool:
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def _open_terminal(command: str, project_root: str) -> bool:
    """
    Open a new terminal window running `command` in `project_root`.
    Returns True if a terminal was launched, False if we fell back to printing.
    """
    if sys.platform == "darwin":
        script = f'tell application "Terminal" to do script "cd {shlex.quote(project_root)} && {command}"'
        subprocess.Popen(["osascript", "-e", script])
        return True

    if sys.platform.startswith("linux"):
        quoted = shlex.quote(project_root)
        for term, args in [
            ("gnome-terminal", ["--", "bash", "-c", f"cd {quoted} && {command}; exec bash"]),
            ("xfce4-terminal", ["-e", f"bash -c 'cd {quoted} && {command}; exec bash'"]),
            ("konsole", ["--noclose", "-e", "bash", "-c", f"cd {quoted} && {command}"]),
            ("xterm", ["-e", f"bash -c 'cd {quoted} && {command}; exec bash'"]),
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


def _make_banner(mcp_url: str) -> str:
    """Shell command that prints the LetsWork banner then launches claude."""
    return (
        f"clear && "
        f"echo '╔══════════════════════════════════════════════════════════╗' && "
        f"echo '║  Claude Code — Connected to LetsWork                     ║' && "
        f"echo '║                                                          ║' && "
        f"echo '║  MCP: {mcp_url}' && "
        f"echo '║                                                          ║' && "
        f"echo '║  Try asking Claude:                                      ║' && "
        f"echo '║    list the files        — browse the host project       ║' && "
        f"echo '║    read <filename>       — view any file                 ║' && "
        f"echo '║    any pending changes?  — check approvals and locks     ║' && "
        f"echo '║                                                          ║' && "
        f"echo '╚══════════════════════════════════════════════════════════╝' && "
        f"echo '' && claude"
    )


def launch_claude_code(project_root: str, tunnel_url: str) -> None:
    """Open a new terminal window with Claude Code for the host."""
    if not shutil.which("claude"):
        print("⚠️  Claude Code not found. Install: npm install -g @anthropic-ai/claude-code")
        return

    mcp_url = f"{tunnel_url}/mcp"

    if _is_wsl():
        print("\n✅ MCP registered. Open a new Ubuntu terminal tab and run:")
        print(f"   cd {project_root} && claude")
        print("")
        return

    launched = _open_terminal(_make_banner(mcp_url), project_root)
    if not launched:
        print("Open a new terminal, cd to your project, and run: claude")


def register_guest_mcp(url: str, token: str) -> None:
    """Register LetsWork as a stdio proxy MCP with Claude Code (blocking).

    Uses stdio transport (always works) rather than HTTP transport (unreliable
    over Cloudflare SSE). The proxy forwards tool calls to the host via HTTP.
    """
    if not shutil.which("claude"):
        print("⚠️  Claude Code not found. Install: npm install -g @anthropic-ai/claude-code")
        return

    proxy_path = shutil.which("letswork-proxy")
    if not proxy_path:
        print("⚠️  letswork-proxy not found. Try: pip install --upgrade letswork")
        return

    # Remove any stale entry from all scopes
    for scope in ("user", "local", "project"):
        subprocess.run(
            ["claude", "mcp", "remove", "letswork", "--scope", scope],
            check=False, capture_output=True, text=True,
        )
    subprocess.run(
        [
            "claude", "mcp", "add", "letswork",
            "--scope", "user",
            "--", proxy_path, "--url", url, "--token", token,
        ],
        check=False, capture_output=True, text=True,
    )


def launch_guest_claude_code(project_root: str, url: str) -> None:
    """Open a new terminal window with Claude Code for the guest."""
    if not shutil.which("claude"):
        print("⚠️  Claude Code not found. Install: npm install -g @anthropic-ai/claude-code")
        return

    if _is_wsl():
        # WSL has no display server — launch claude directly in this terminal
        # Create a temp session directory with CLAUDE.md so Claude knows to use MCP tools
        temp_dir = tempfile.mkdtemp(prefix="letswork-session-")
        try:
            with open(os.path.join(temp_dir, "CLAUDE.md"), "w", encoding="utf-8") as f:
                f.write(
                    "# LetsWork Guest Session\n\n"
                    "You are a guest collaborating on a remote project. "
                    "The host's project files are only accessible through LetsWork MCP tools — "
                    "do NOT use local file system tools (Read, Write, Bash, Glob) for project files.\n\n"
                    "IMPORTANT: At the start of the session, ask the user for their name and call "
                    "`mcp__letswork__set_display_name` with it so the host can identify them.\n\n"
                    "Use these tools for all file operations on the host's project:\n"
                    "- `mcp__letswork__set_display_name` — set your display name (do this first)\n"
                    "- `mcp__letswork__list_files` — list files\n"
                    "- `mcp__letswork__read_file` — read a file\n"
                    "- `mcp__letswork__write_file` — submit a change (requires host approval)\n"
                    "- `mcp__letswork__lock_file` — lock a file before editing\n"
                    "- `mcp__letswork__unlock_file` — unlock when done\n"
                    "- `mcp__letswork__get_notifications` — check pending changes and locks\n"
                    "- `mcp__letswork__my_pending_changes` — check your submitted changes\n"
                    "- `mcp__letswork__ping` — verify connection to host\n"
                )
            print("\n✅ MCP registered. Launching Claude Code...\n")
            print("  Try asking Claude:")
            print('    "list the files"        — browse the host project')
            print('    "read <filename>"       — view any file')
            print('    "any pending changes?"  — check approvals & locks')
            print("")
            subprocess.run(["claude"], cwd=temp_dir)
        except KeyboardInterrupt:
            pass
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return

    launched = _open_terminal(_make_banner(url), project_root)
    if not launched:
        print(f"\n✅ MCP registered. Open a new terminal and run:")
        print(f"   claude")


