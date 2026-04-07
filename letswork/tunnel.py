import subprocess
import shutil
import re
import platform
import sys


def _cloudflared_install_hint() -> str:
    os_name = platform.system()
    if os_name == "Darwin":
        return "  brew install cloudflared"
    elif os_name == "Linux":
        return (
            "  # Debian/Ubuntu:\n"
            "  curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null\n"
            "  echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list\n"
            "  sudo apt update && sudo apt install cloudflared\n\n"
            "  # Or direct binary download:\n"
            "  curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared\n"
            "  chmod +x cloudflared && sudo mv cloudflared /usr/local/bin/"
        )
    elif os_name == "Windows":
        return "  winget install Cloudflare.cloudflared"
    else:
        return "  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"


def start_tunnel(port: int) -> tuple[str, subprocess.Popen]:
    """Start a Cloudflare tunnel pointing to the local MCP server port. Returns the HTTPS URL and the subprocess handle."""
    if shutil.which("cloudflared") is None:
        hint = _cloudflared_install_hint()
        print("\n[letswork] cloudflared is required to share your session over the internet.", file=sys.stderr)
        print("[letswork] Install it with:\n", file=sys.stderr)
        print(hint, file=sys.stderr)
        print("", file=sys.stderr)
        raise RuntimeError("cloudflared not found — see install instructions above")
        
    command = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    timeout_counter = 0
    while True:
        line = process.stderr.readline().decode("utf-8").strip()
        
        if not line and process.poll() is not None:
            raise RuntimeError("cloudflared exited unexpectedly")
            
        match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
        if match:
            return match.group(0), process
            
        timeout_counter += 1
        if timeout_counter >= 30:
            process.terminate()
            raise RuntimeError("Failed to start tunnel: could not find tunnel URL in cloudflared output")


def stop_tunnel(process: subprocess.Popen) -> None:
    """Gracefully terminate the cloudflared subprocess."""
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
