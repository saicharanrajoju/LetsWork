import requests
import json
import uuid


class RemoteClient:
    """Calls LetsWork MCP tools over HTTP. Guest TUI uses this instead of local file access."""

    def __init__(self, mcp_url: str, token: str):
        self.mcp_url = mcp_url.rstrip("/")
        self.token = token
        self.session_id: str | None = None

    def _call_mcp(self, method: str, params: dict = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {}
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        try:
            response = requests.post(self.mcp_url, json=payload, headers=headers, timeout=15)
            if "Mcp-Session-Id" in response.headers:
                self.session_id = response.headers["Mcp-Session-Id"]
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                # Parse the last "data:" line as JSON
                last_data = None
                for line in response.text.splitlines():
                    if line.startswith("data:"):
                        last_data = line[len("data:"):].strip()
                if last_data:
                    return json.loads(last_data)
                return {}
            return response.json()
        except Exception:
            return {}

    def initialize(self) -> bool:
        try:
            self._call_mcp("initialize", {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "letswork-guest", "version": "1.0"}
            })
            self._call_mcp("notifications/initialized", {})
            return True
        except Exception:
            return False

    def call_tool(self, tool_name: str, arguments: dict = None) -> str:
        try:
            result = self._call_mcp("tools/call", {"name": tool_name, "arguments": arguments or {}})
            try:
                return result["result"]["content"][0]["text"]
            except (KeyError, IndexError, TypeError):
                return str(result)
        except requests.RequestException:
            return "Error: connection failed"

    def list_files(self, path: str = ".") -> str:
        return self.call_tool("list_files", {"path": path})

    def read_file(self, path: str) -> str:
        return self.call_tool("read_file", {"path": path})

    def write_file(self, path: str, content: str, user_id: str) -> str:
        return self.call_tool("write_file", {"path": path, "content": content, "user_id": user_id})

    def lock_file(self, path: str, user_id: str) -> str:
        return self.call_tool("lock_file", {"path": path, "user_id": user_id})

    def unlock_file(self, path: str, user_id: str) -> str:
        return self.call_tool("unlock_file", {"path": path, "user_id": user_id})

    def send_message(self, user_id: str, message: str) -> str:
        return self.call_tool("send_message", {"user_id": user_id, "message": message})

    def get_events(self, since_index: int = 0) -> str:
        return self.call_tool("get_events", {"since_index": since_index})

    def get_status(self) -> str:
        return self.call_tool("get_status", {})
