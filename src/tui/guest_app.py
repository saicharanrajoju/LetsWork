import os
import time
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Static, RichLog, Tree, Input
from textual.containers import Vertical, ScrollableContainer
from rich.syntax import Syntax
from src.remote_client import RemoteClient
from src.events import EventLog, EventType


class GuestApp(App):
    TITLE = "LetsWork"
    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 2fr;
        grid-rows: 3fr 1fr;
    }

    #file-tree-panel {
        border: solid green;
        height: 100%;
        overflow-y: auto;
    }

    #file-viewer-panel {
        border: solid blue;
        height: 100%;
        overflow-y: auto;
    }

    #activity-panel {
        border: solid yellow;
        height: 100%;
        overflow-y: auto;
    }

    #chat-panel {
        border: solid cyan;
        height: 100%;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "^Q Quit"),
    ]

    def __init__(self, mcp_url: str, token: str, user_id: str = "guest", **kwargs):
        super().__init__(**kwargs)
        self.client = RemoteClient(mcp_url, token)
        self.user_id = user_id
        self._event_index = 0
        self._current_file = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Tree("📁 Project", id="file-tree-panel")
            yield ScrollableContainer(Static("📄 Select a file to view", id="viewer-display"), id="file-viewer-panel")
            yield RichLog(id="activity-panel", markup=True, highlight=True, wrap=True)
            yield Vertical(
                RichLog(id="chat-messages", markup=True, highlight=True, wrap=True),
                Input(placeholder="Type a message and press Enter...", id="chat-input"),
                id="chat-panel"
            )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"Guest: {self.user_id} — Connected via MCP"
        try:
            self.client.initialize()
        except Exception:
            pass
        activity = self.query_one("#activity-panel", RichLog)
        activity.write("[bold yellow]📡 Activity Log[/bold yellow]")
        activity.write(f"[bold green]✅ Connected as {self.user_id}[/bold green]")
        chat = self.query_one("#chat-messages", RichLog)
        chat.write("[bold cyan]💬 Chat[/bold cyan]")
        self._load_remote_tree()
        self.set_interval(1.0, self._poll_remote_events)

    def _load_remote_tree(self) -> None:
        try:
            result = self.client.list_files(".")
            tree = self.query_one("#file-tree-panel", Tree)
            tree.root.remove_children()
            tree.root.expand()
            for line in result.strip().split("\n"):
                if not line.strip():
                    continue
                line = line.strip()
                if line.startswith("[dir]"):
                    name = line.replace("[dir]", "").strip()
                    node = tree.root.add(f"📁 {name}", data={"path": name, "is_dir": True})
                    self._load_remote_subdir(node, name)
                elif line.startswith("[file]"):
                    parts = line.replace("[file]", "").strip()
                    name = parts.split("[")[0].strip()
                    lock_info = ""
                    if "locked by" in parts:
                        lock_info = " 🔒" + parts[parts.index("[locked"):]
                    tree.root.add_leaf(f"📄 {name}{lock_info}", data={"path": name, "is_dir": False})
        except Exception as e:
            activity = self.query_one("#activity-panel", RichLog)
            activity.write(f"[red]Error loading files: {e}[/red]")

    def _load_remote_subdir(self, parent_node, path: str) -> None:
        try:
            result = self.client.list_files(path)
            for line in result.strip().split("\n"):
                if not line.strip():
                    continue
                line = line.strip()
                if line.startswith("[dir]"):
                    name = line.replace("[dir]", "").strip()
                    dir_name = name.split("/")[-1] if "/" in name else name
                    full_path = name if "/" in name else f"{path}/{name}"
                    node = parent_node.add(f"📁 {dir_name}", data={"path": full_path, "is_dir": True})
                    self._load_remote_subdir(node, full_path)
                elif line.startswith("[file]"):
                    parts = line.replace("[file]", "").strip()
                    name = parts.split("[")[0].strip()
                    file_name = name.split("/")[-1] if "/" in name else name
                    full_path = name if "/" in name else f"{path}/{name}"
                    lock_info = ""
                    if "locked by" in parts:
                        lock_info = " 🔒" + parts[parts.index("[locked"):]
                    parent_node.add_leaf(f"📄 {file_name}{lock_info}", data={"path": full_path, "is_dir": False})
        except Exception:
            pass

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node_data = event.node.data
        if node_data is None or node_data.get("is_dir", False):
            return
        file_path = node_data.get("path", "")
        if not file_path:
            return
        try:
            content = self.client.read_file(file_path)
            self._current_file = file_path
            ext = os.path.splitext(file_path)[1].lower()
            lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".html": "html", ".css": "css", ".json": "json", ".md": "markdown", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".sh": "bash"}
            language = lang_map.get(ext, "text")
            syntax = Syntax(content, language, theme="monokai", line_numbers=True, word_wrap=True)
            display = self.query_one("#viewer-display", Static)
            display.update(syntax)
            activity = self.query_one("#activity-panel", RichLog)
            activity.write(f"📖 Opened {file_path}")
        except Exception as e:
            display = self.query_one("#viewer-display", Static)
            display.update(f"Error reading {file_path}: {e}")

    def _poll_remote_events(self) -> None:
        try:
            result = self.client.get_events(self._event_index)
            if result == "no_new_events" or not result:
                return
            lines = result.strip().split("\n")
            activity = self.query_one("#activity-panel", RichLog)
            chat = self.query_one("#chat-messages", RichLog)
            for line in lines:
                if line.startswith("__INDEX__:"):
                    self._event_index = int(line.replace("__INDEX__:", ""))
                elif "💬" in line:
                    chat.write(line)
                    activity.write(line)
                elif line.strip():
                    activity.write(line)
            self._load_remote_tree()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        message = event.value.strip()
        if not message:
            return
        event.input.value = ""
        try:
            self.client.send_message(self.user_id, message)
        except Exception as e:
            chat = self.query_one("#chat-messages", RichLog)
            chat.write(f"[red]Failed to send: {e}[/red]")

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m src.tui.guest_app <mcp_url> <token> [username]")
        sys.exit(1)
    url = sys.argv[1]
    token = sys.argv[2]
    user = sys.argv[3] if len(sys.argv) > 3 else "guest"
    app = GuestApp(mcp_url=url, token=token, user_id=user)
    app.run()
