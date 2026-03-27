import subprocess
import shutil
import re


def start_tunnel(port: int) -> tuple[str, subprocess.Popen]:
    """Start a Cloudflare tunnel pointing to the local MCP server port. Returns the HTTPS URL and the subprocess handle."""
    if shutil.which("cloudflared") is None:
        raise RuntimeError("cloudflared is not installed. Install it from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        
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
