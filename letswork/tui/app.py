import os
from rich.text import Text
from letswork.tui.approval_panel import ApprovalPanel
from letswork.tui.chat import ChatWidget
from letswork.events import EventLog, Event, EventType
from letswork.tui.file_viewer import FileViewerWidget
from textual.widgets import Tree
from letswork.tui.file_tree import FileTreeWidget
from letswork.filelock import LockManager
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, RichLog
from letswork.remote_client import RemoteClient

class LetsWorkApp(App):
    TITLE = "LetsWork"
    SUB_TITLE = "Collaborative Coding Dashboard"
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+e", "toggle_edit", "Edit File"),
        ("ctrl+s", "submit_change", "Save"),
        ("escape", "cancel_edit", "Cancel"),
    ]

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 1fr 3fr;
        grid-rows: 5fr 2fr 1fr;
    }
    #file-tree-panel {
        border: solid $secondary;
        height: 100%;
        overflow-y: auto;
        scrollbar-gutter: stable;
    }
    #file-viewer-panel {
        border: solid $primary;
        height: 100%;
        overflow-y: auto;
    }
    #activity-panel {
        border: solid $warning;
        height: 100%;
        overflow-y: auto;
    }
    #chat-panel {
        border: solid $accent;
        height: 100%;
        overflow-y: auto;
    }
    #approval-panel {
        border: solid $error;
        column-span: 2;
        height: 100%;
        overflow-y: auto;
    }
    .panel-title {
        text-style: bold;
    }
    .guest-mode #main-container {
        grid-size: 2 2;
        grid-rows: 5fr 2fr;
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
        self.remote_client: RemoteClient | None = None
        if self.guest_mode and self.mcp_url and self.mcp_token:
            self.remote_client = RemoteClient(self.mcp_url, self.mcp_token)
        self._last_event_count = 0
        self._file_mtimes: dict[str, float] = {}
        self._guest_poll_in_progress = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield FileTreeWidget(self.project_root, self.lock_manager,
                                 remote_client=self.remote_client, id="file-tree-panel")
            yield FileViewerWidget(remote_client=self.remote_client, id="file-viewer-panel")
            yield RichLog(id="activity-panel", markup=True, highlight=True, wrap=True)
            yield ChatWidget(self.event_log, user_id=self.user_id, remote_client=self.remote_client if self.guest_mode else None, id="chat-panel")
            if self.approval_queue is not None:
                yield ApprovalPanel(self.approval_queue, self.event_log, id="approval-panel")
        yield Footer()

    def on_mount(self) -> None:
        import threading

        if self.guest_mode:
            self.add_class("guest-mode")
            self.sub_title = f"Guest: {self.user_id} — {self.mcp_url}"
        else:
            self.sub_title = f"Host — {self.project_root}"

        activity = self.query_one("#activity-panel", RichLog)
        activity.write("[bold yellow]📡 Activity Log[/bold yellow]")
        activity.write("Waiting for connections...")

        self.set_interval(0.5, self._poll_events)
        self.set_interval(1.0, self._poll_file_changes)
        self._last_event_count = len(self.event_log._events)
        for past_event in self.event_log.get_recent():
            activity.write(past_event.message)

        if self.remote_client:
            activity.write("[dim]Connecting to host...[/dim]")
            threading.Thread(target=self._connect_to_host, daemon=True).start()

    def _connect_to_host(self) -> None:
        connected = self.remote_client.connect()

        def _update():
            activity = self.query_one("#activity-panel", RichLog)
            if connected:
                activity.write("[bold green]✅ Connected to host[/bold green]")
                try:
                    tree = self.query_one("#file-tree-panel", FileTreeWidget)
                    # Force-reset the flag (on_mount may have set it before connection)
                    # and call refresh_tree directly on the main thread — it only
                    # spawns a background worker so this is safe.
                    tree._refresh_in_progress = False
                    tree.refresh_tree()
                except Exception:
                    pass
            else:
                activity.write("[bold red]❌ Failed to connect to host[/bold red]")

        self.call_from_thread(_update)

    def _poll_file_changes(self) -> None:
        """Watch for local file changes and update TUI."""
        if self.guest_mode:
            return
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
        if self.guest_mode and self.remote_client:
            if self._guest_poll_in_progress:
                return
            self._guest_poll_in_progress = True
            import threading
            threading.Thread(target=self._fetch_guest_events, daemon=True).start()
            return
        # Original local event polling below — keep unchanged
        current_count = len(self.event_log._events)
        if current_count > self._last_event_count:
            new_events = self.event_log._events[self._last_event_count:current_count]
            self._last_event_count = current_count
            try:
                activity = self.query_one("#activity-panel", RichLog)
                for event in new_events:
                    if event.event_type == EventType.ERROR:
                        activity.write(Text(event.message, style="bold red"))
                    else:
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
        lock_count = len(self.lock_manager.get_locks()) if hasattr(self, 'lock_manager') else 0
        lock_info = f" — 🔒 {lock_count} locks" if lock_count > 0 else ""
        if self.guest_mode:
            base = f"Guest: {self.user_id} — {self.mcp_url}"
        else:
            base = f"Host — {self.project_root}"
        self.sub_title = base + lock_info

    def _fetch_guest_events(self) -> None:
        """Background thread: fetch events from MCP server, update UI safely."""
        try:
            result = self.remote_client.get_events(self._last_event_count)
            if result == "no_new_events" or result.startswith("Error"):
                return
            lines = result.strip().split("\n")
            new_index = self._last_event_count
            display_lines = []
            for line in lines:
                if line.startswith("__INDEX__:"):
                    try:
                        new_index = int(line.split(":")[1])
                    except (ValueError, IndexError):
                        pass
                else:
                    display_lines.append(line)

            def _update():
                self._last_event_count = new_index
                activity = self.query_one("#activity-panel", RichLog)
                for line in display_lines:
                    activity.write(line)
                try:
                    tree = self.query_one("#file-tree-panel", FileTreeWidget)
                    import threading
                    threading.Thread(target=tree.refresh_tree, daemon=True).start()
                except Exception:
                    pass

            self.call_from_thread(_update)
        except Exception as e:
            def _update_error():
                activity = self.query_one("#activity-panel", RichLog)
                activity.write(Text(f"❌ Connection error: {e}", style="bold red"))
            self.call_from_thread(_update_error)
        finally:
            self._guest_poll_in_progress = False

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
        if self.guest_mode and self.remote_client:
            result = viewer.submit_remote()
            activity = self.query_one("#activity-panel", RichLog)
            if "Error" in result:
                activity.write(f"[bold red]❌ {result}[/bold red]")
            else:
                activity.write(f"[bold green]✅ {result}[/bold green]")
            viewer.toggle_edit()
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
        if self.remote_client:
            self.remote_client.disconnect()
        self.exit()

if __name__ == "__main__":
    from letswork.events import EventLog
    event_log = EventLog()
    app = LetsWorkApp(project_root=os.getcwd(), event_log=event_log)
    app.run()
