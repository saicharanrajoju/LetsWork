import subprocess
import shutil
import sys


def launch_with_claude_code(project_root: str, tunnel_url: str, token: str, port: int) -> None:
    """Open a new Terminal tab with Claude Code, then launch TUI in current terminal."""

    if sys.platform == "darwin":
        # Mac: open new Terminal tab with Claude Code
        claude_path = shutil.which("claude")
        if claude_path:
            apple_script = f'''
            tell application "Terminal"
                activate
                do script "cd {project_root} && clear && echo '╔══════════════════════════════════════════════════╗' && echo '║  🤖 Claude Code — Connected to LetsWork          ║' && echo '║                                                  ║' && echo '║  MCP URL: {tunnel_url}/mcp' && echo '║  Token: {token}' && echo '║                                                  ║' && echo '║  Try: list_files, read_file, write_file           ║' && echo '╚══════════════════════════════════════════════════╝' && echo '' && claude"
            end tell
            '''
            subprocess.Popen(["osascript", "-e", apple_script])
        else:
            print("⚠️  Claude Code not found. Install with: npm install -g @anthropic-ai/claude-code")
            print("   Open a second terminal and run: claude")
    else:
        # Linux/Windows: just print instructions
        print("Open a second terminal and run:")
        print(f"  cd {project_root}")
        print("  claude")
        print("Claude Code will connect to your LetsWork MCP server automatically.")

    # Launch TUI in current terminal
    import src.server as server_module
    from src.tui.app import LetsWorkApp

    app = LetsWorkApp(
        project_root=project_root,
        lock_manager=server_module.lock_manager,
        event_log=server_module.event_log,
        approval_queue=server_module.approval_queue,
    )
    app.run()


def launch_guest_claude_code(url: str, token: str) -> None:
    print("[LetsWork] Configuring Claude Code for guest connection...")
    result = subprocess.run(
        ["claude", "mcp", "add", "letswork", "--transport", "http", url],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("[LetsWork] Warning: Could not auto-configure MCP. You may need to run manually:")
        print(f"  claude mcp add letswork --transport http {url}")

    print("[LetsWork] MCP server added. Opening Claude Code...")

    if sys.platform == "darwin":
        script = '''
        tell application "Terminal"
            activate
            do script "claude"
        end tell
        '''
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        print("[LetsWork] Auto-launch not supported on this OS.")
        print("[LetsWork] Open a new terminal and run: claude")

    print("[LetsWork] Guest Claude Code is ready. Use MCP tools to collaborate.")

