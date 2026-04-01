import asyncio
import threading
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

_RECONNECT_DELAYS = [1, 2, 5, 10, 30]  # seconds between retries


class RemoteClient:
    """
    Connects to Host MCP server over streamable-http,
    exposes sync methods for TUI widgets.
    Auto-reconnects if the connection drops.
    """
    def __init__(self, mcp_url: str, token: str):
        self.mcp_url = mcp_url
        self.token = token
        self._session: ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._connected = False
        self._should_run = False
        self._on_reconnect: callable | None = None

    def on_reconnect(self, callback: callable) -> None:
        """Register a callback invoked after each successful reconnect."""
        self._on_reconnect = callback

    def connect(self) -> bool:
        self._should_run = True
        loop = asyncio.new_event_loop()
        self._loop = loop
        ready_event = threading.Event()

        async def _run_loop():
            attempt = 0
            while self._should_run:
                try:
                    async with streamablehttp_client(self.mcp_url) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            self._session = session
                            self._connected = True
                            attempt = 0
                            ready_event.set()
                            if self._on_reconnect:
                                self._on_reconnect()
                            while self._connected and self._should_run:
                                await asyncio.sleep(0.1)
                except Exception:
                    self._connected = False
                    self._session = None
                    if not ready_event.is_set():
                        # First connect failed — signal caller and stop retrying
                        ready_event.set()
                        return
                    # Reconnect with backoff
                    delay = _RECONNECT_DELAYS[min(attempt, len(_RECONNECT_DELAYS) - 1)]
                    attempt += 1
                    await asyncio.sleep(delay)

        def thread_target():
            loop.run_until_complete(_run_loop())

        self._thread = threading.Thread(target=thread_target, daemon=True)
        self._thread.start()

        ready_event.wait(timeout=10)
        return self._connected

    def disconnect(self):
        self._should_run = False
        self._connected = False
        if self._thread:
            self._thread.join(timeout=5)
        self._session = None
        self._loop = None

    def _run_async(self, coro) -> any:
        if not self._connected or self._loop is None:
            raise RuntimeError("Not connected")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=15)

    def _call_tool(self, tool_name: str, arguments: dict) -> str:
        if not self._connected or self._session is None:
            return "Error: not connected"
        try:
            result = self._run_async(
                self._session.call_tool(tool_name, arguments)
            )
            for item in result.content:
                if item.type == "text":
                    return item.text
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def list_files(self, path: str = ".") -> str:
        return self._call_tool("list_files", {"token": self.token, "path": path})

    def read_file(self, path: str) -> str:
        return self._call_tool("read_file", {"token": self.token, "path": path})

    def write_file(self, path: str, content: str) -> str:
        return self._call_tool("write_file", {"token": self.token, "path": path, "content": content})

    def lock_file(self, path: str) -> str:
        return self._call_tool("lock_file", {"token": self.token, "path": path})

    def unlock_file(self, path: str) -> str:
        return self._call_tool("unlock_file", {"token": self.token, "path": path})

    def register_name(self, display_name: str) -> str:
        return self._call_tool("register_name", {"token": self.token, "display_name": display_name})

    def send_message(self, message: str) -> str:
        return self._call_tool("send_message", {"token": self.token, "message": message})

    def get_events(self, since_index: int = 0) -> str:
        return self._call_tool("get_events", {"token": self.token, "since_index": since_index})

    def get_status(self) -> str:
        return self._call_tool("get_status", {"token": self.token})
