import os
from src.tui.approval_panel import ApprovalPanel
from src.tui.chat import ChatWidget
from src.events import EventLog, Event, EventType
from src.tui.file_viewer import FileViewerWidget
from textual.widgets import Tree
from src.tui.file_tree import FileTreeWidget
from src.filelock import LockManager
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, RichLog

class LetsWorkApp(App):
    TITLE = "LetsWork"
    SUB_TITLE = "Collaborative Coding Dashboard"
    BINDINGS = [
        ("ctrl+q", "quit", "^Q Quit"),
        ("ctrl+e", "toggle_edit", "^E Edit"),
        ("ctrl+s", "submit_change", "^S Submit"),
        ("escape", "cancel_edit", "Esc Cancel"),
    ]

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 1fr 2fr;
        grid-rows: 3fr 1fr 1fr;
    }

    #file-tree-panel {
        border: solid green;
        height: 100%;
        overflow-y: auto;
        scrollbar-gutter: stable;
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

    #approval-panel {
        border: solid magenta;
        column-span: 2;
        height: 100%;
        overflow-y: auto;
    }

    .panel-title {
        text-style: bold;
    }

    .guest-mode #main-container {
        grid-size: 2 2;
        grid-rows: 3fr 1fr;
    }
    """

    def __init__(self, project_root: str = "", lock_manager=None, event_log=None, approval_queue=None, guest_mode: bool = False, mcp_url: str = "", mcp_token: str = "", user_id: str = "host", **kwargs):
        super().__init__(**kwargs)
        self.project_root = project_root or os.getcwd()
        self.lock_manager = lock_manager or LockManager()
        self.event_log = event_log or EventLog()
        self.approval_queue = approval_queue
        self.guest_mode = guest_mode
        self.mcp_url = mcp_url
        self.mcp_token = mcp_token
        self.user_id = user_id
        self._last_event_count = 0
        self._file_mtimes: dict[str, float] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield FileTreeWidget(self.project_root, self.lock_manager, id="file-tree-panel")
            yield FileViewerWidget(id="file-viewer-panel")
            yield RichLog(id="activity-panel", markup=True, highlight=True, wrap=True)
            yield ChatWidget(self.event_log, user_id=self.user_id, id="chat-panel")
            if self.approval_queue is not None:
                yield ApprovalPanel(self.approval_queue, self.event_log, id="approval-panel")
        yield Footer()

    def on_mount(self) -> None:
        if self.guest_mode:
            self.add_class("guest-mode")
            self.sub_title = f"Guest: {self.user_id} — Connected to {self.mcp_url}"

        activity = self.query_one("#activity-panel", RichLog)
        activity.write("[bold yellow]📡 Activity Log[/bold yellow]")
        activity.write("Waiting for connections...")

        self.set_interval(0.5, self._poll_events)
        self.set_interval(1.0, self._poll_file_changes)
        self._last_event_count = len(self.event_log._events)
        for past_event in self.event_log.get_recent():
            activity.write(past_event.message)

    def _poll_file_changes(self) -> None:
        """Watch for local file changes and update TUI."""
        try:
            # Check if currently viewed file has changed on disk
            viewer = self.query_one("#file-viewer-panel", FileViewerWidget)
            if viewer.current_file:
                abs_path = os.path.join(self.project_root, viewer.current_file)
                if os.path.isfile(abs_path):
                    mtime = os.path.getmtime(abs_path)
                    old_mtime = self._file_mtimes.get(viewer.current_file)
                    if old_mtime is not None and mtime != old_mtime:
                        # File changed on disk — reload viewer
                        viewer.load_file(viewer.current_file, self.project_root)
                        try:
                            activity = self.query_one("#activity-panel", RichLog)
                            try:
                                with open(abs_path, "r", encoding="utf-8") as f:
                                    new_content = f.read()
                                line_count = len(new_content.strip().split("\n"))
                                activity.write(f"[bold]🔄 {viewer.current_file} modified — {line_count} lines — refreshed[/bold]")
                            except Exception:
                                activity.write(f"[bold]🔄 {viewer.current_file} changed on disk — refreshed[/bold]")
                        except Exception:
                            pass
                    self._file_mtimes[viewer.current_file] = mtime
        except Exception:
            pass

        try:
            # Refresh file tree periodically to catch new/deleted files
            tree = self.query_one("#file-tree-panel", FileTreeWidget)
            tree.refresh_tree()
        except Exception:
            pass

        # Scan for new files in project root to log in activity
        try:
            for root_dir, dirs, files in os.walk(self.project_root):
                # Skip hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "node_modules" and d != ".venv" and d != "venv"]
                for fname in files:
                    if fname.startswith(".") or fname.endswith(".pyc"):
                        continue
                    rel = os.path.relpath(os.path.join(root_dir, fname), self.project_root)
                    fpath = os.path.join(root_dir, fname)
                    mtime = os.path.getmtime(fpath)
                    if rel not in self._file_mtimes:
                        self._file_mtimes[rel] = mtime
                    elif mtime != self._file_mtimes[rel]:
                        self._file_mtimes[rel] = mtime
                        activity = self.query_one("#activity-panel", RichLog)
                        activity.write(f"[bold yellow]✏️  {rel} modified on disk[/bold yellow]")
        except Exception:
            pass

    def _poll_events(self) -> None:
        """Periodically check for new events from the MCP server thread."""
        current_count = len(self.event_log._events)
        if current_count > self._last_event_count:
            new_events = self.event_log._events[self._last_event_count:current_count]
            self._last_event_count = current_count
            try:
                activity = self.query_one("#activity-panel", RichLog)
                for event in new_events:
                    activity.write(event.message)
            except Exception:
                pass
            # Refresh file tree to show new lock status
            try:
                tree = self.query_one("#file-tree-panel", FileTreeWidget)
                tree.refresh_tree()
            except Exception:
                pass
            # Auto-refresh file viewer if viewed file was changed
            try:
                viewer = self.query_one("#file-viewer-panel", FileViewerWidget)
                if viewer.current_file:
                    for event in new_events:
                        if event.event_type == EventType.FILE_WRITE:
                            status = event.data.get("status")
                            if event.data.get("path") == viewer.current_file and (status == "approved" or status is None):
                                viewer.load_file(viewer.current_file, self.project_root)
                                break
            except Exception:
                pass

    def handle_event(self, event: Event) -> None:
        pass

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle file tree node click — load file in viewer."""
        node_data = event.node.data
        if node_data is None:
            return
        if node_data.get("is_dir", False):
            return
        file_path = node_data.get("path", "")
        if not file_path:
            return
        viewer = self.query_one("#file-viewer-panel", FileViewerWidget)
        viewer.load_file(file_path, self.project_root)
        activity = self.query_one("#activity-panel", RichLog)
        activity.write(f"📖 Opened {file_path}")

    def action_toggle_edit(self) -> None:
        """Toggle edit mode on the file viewer."""
        viewer = self.query_one("#file-viewer-panel", FileViewerWidget)
        if not viewer.current_file:
            return
        viewer.toggle_edit()
        activity = self.query_one("#activity-panel", RichLog)
        if viewer.edit_mode:
            activity.write(f"[bold]✏️  Editing {viewer.current_file} — press [S] to submit, [Escape] to cancel[/bold]")
        else:
            activity.write("[dim]Exited edit mode[/dim]")

    def action_submit_change(self) -> None:
        """Submit the edited content directly to disk."""
        viewer = self.query_one("#file-viewer-panel", FileViewerWidget)
        if not viewer.edit_mode or not viewer.current_file:
            return
        new_content = viewer.get_editor_content()
        abs_path = os.path.join(self.project_root, viewer.current_file)
        try:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            self.event_log.emit(EventType.FILE_WRITE, self.user_id, {"path": viewer.current_file, "status": None})
            activity = self.query_one("#activity-panel", RichLog)
            activity.write(f"[bold green]✅ {viewer.current_file} saved[/bold green]")
        except Exception as e:
            activity = self.query_one("#activity-panel", RichLog)
            activity.write(f"[bold red]❌ Failed to save {viewer.current_file}: {e}[/bold red]")
        # Exit edit mode
        viewer.toggle_edit()

    def action_cancel_edit(self) -> None:
        """Cancel edit mode without submitting."""
        viewer = self.query_one("#file-viewer-panel", FileViewerWidget)
        if viewer.edit_mode:
            viewer.toggle_edit()
            activity = self.query_one("#activity-panel", RichLog)
            activity.write("[dim]Edit cancelled[/dim]")

    def action_quit(self) -> None:
        self.exit()

if __name__ == "__main__":
    from src.events import EventLog
    event_log = EventLog()
    app = LetsWorkApp(project_root=os.getcwd(), event_log=event_log)
    app.run()
