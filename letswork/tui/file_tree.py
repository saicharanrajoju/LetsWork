import os
import threading
from rich.text import Text
from textual.widgets import Tree


class FileTreeWidget(Tree):
    def __init__(self, project_root: str, lock_manager, remote_client=None, **kwargs):
        self.project_root = project_root
        self.lock_manager = lock_manager
        self.remote_client = remote_client
        self._refresh_in_progress = False
        super().__init__("📁 Project", **kwargs)

    def on_mount(self) -> None:
        # Remote mode: wait for _connect_to_host to call refresh_tree()
        if self.remote_client is None:
            self._add_directory(self.root, self.project_root, "")
        self.root.expand()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazy-load directory contents when a node is expanded."""
        node = event.node
        if not (node.data and node.data.get("is_dir")):
            return
        if node.data.get("loaded"):
            return
        # Mark loading so we don't double-fetch
        node.data["loaded"] = True
        path = node.data["path"]
        threading.Thread(
            target=self._load_directory, args=(node, path), daemon=True
        ).start()

    def _load_directory(self, node, path: str) -> None:
        """Fetch one directory level in background, populate node on main thread."""
        listing = self.remote_client.list_files(path)

        dirs_list = []
        files_list = []
        if listing and not listing.startswith("Error") and listing != "Directory is empty":
            for line in listing.splitlines():
                p, is_dir, holder = self._parse_listing_line(line)
                if not p:
                    continue
                name = p.split("/")[-1] if "/" in p else p.split("\\")[-1] if "\\" in p else p
                if self.should_ignore(name):
                    continue
                if is_dir:
                    dirs_list.append((name, p))
                else:
                    files_list.append((name, p, holder))

        dirs_list.sort(key=lambda x: x[0].lower())
        files_list.sort(key=lambda x: x[0].lower())

        def _populate():
            # Remove the "(loading...)" placeholder
            node.remove_children()
            for dir_name, full_rel_path in dirs_list:
                child = node.add(
                    Text(f"📁 {dir_name}", style="bold cyan"),
                    data={"path": full_rel_path, "is_dir": True, "loaded": False},
                )
                # Add placeholder so the node shows as expandable
                child.add_leaf(Text("  (loading...)", style="dim"))
            for file_name, full_rel_path, holder in files_list:
                if holder:
                    label = Text(f"  {file_name} 🔒 {holder}", style="bold red")
                else:
                    label = Text(f"  {file_name}", style="white")
                node.add_leaf(label, data={"path": full_rel_path, "is_dir": False})
            if not dirs_list and not files_list:
                node.add_leaf(Text("  (empty)", style="dim"))

        self.call_from_thread(_populate)

    def refresh_tree(self) -> None:
        if self.remote_client is not None:
            if self._refresh_in_progress:
                return
            self._refresh_in_progress = True
            threading.Thread(target=self._background_refresh, daemon=True).start()
        else:
            self.root.remove_children()
            self._add_directory(self.root, self.project_root, "")
            self.root.expand()

    def _background_refresh(self) -> None:
        """Fetch root level only. Subdirectories load lazily on expand."""
        listing = self.remote_client.list_files(".")
        dirs_list = []
        files_list = []
        error_msg = None

        if not listing or listing.startswith("Error") or listing == "Directory is empty":
            error_msg = repr(listing[:80]) if listing else "empty response"
        else:
            for line in listing.splitlines():
                p, is_dir, holder = self._parse_listing_line(line)
                if not p:
                    continue
                name = p.split("/")[-1] if "/" in p else p.split("\\")[-1] if "\\" in p else p
                if self.should_ignore(name):
                    continue
                if is_dir:
                    dirs_list.append((name, p))
                else:
                    files_list.append((name, p, holder))

            dirs_list.sort(key=lambda x: x[0].lower())
            files_list.sort(key=lambda x: x[0].lower())

        def _rebuild():
            self.root.remove_children()
            if error_msg:
                self.root.add_leaf(f"(error: {error_msg})")
            else:
                for dir_name, full_rel_path in dirs_list:
                    child = self.root.add(
                        Text(f"📁 {dir_name}", style="bold cyan"),
                        data={"path": full_rel_path, "is_dir": True, "loaded": False},
                    )
                    # Placeholder makes the node show as expandable
                    child.add_leaf(Text("  (loading...)", style="dim"))
                for file_name, full_rel_path, holder in files_list:
                    if holder:
                        label = Text(f"  {file_name} 🔒 {holder}", style="bold red")
                    else:
                        label = Text(f"  {file_name}", style="white")
                    self.root.add_leaf(label, data={"path": full_rel_path, "is_dir": False})
            self.root.expand()
            self._refresh_in_progress = False

        self.call_from_thread(_rebuild)

    def _parse_listing_line(self, line: str) -> tuple[str, bool, str | None]:
        line = line.strip()
        if line.startswith("[dir] "):
            return (line[6:].strip(), True, None)
        if line.startswith("[file] "):
            rest = line[7:].strip()
            if " [locked by " in rest:
                parts = rest.split(" [locked by ", 1)
                return (parts[0], False, parts[1].rstrip("]"))
            return (rest, False, None)
        return ("", False, None)

    def _add_directory(self, parent_node, abs_path: str, rel_path: str) -> None:
        try:
            entries = os.listdir(abs_path)
        except OSError:
            return

        dirs_list = []
        files_list = []
        for entry in entries:
            full_path = os.path.join(abs_path, entry)
            if self.should_ignore(entry):
                continue
            if os.path.isdir(full_path):
                dirs_list.append(entry)
            else:
                files_list.append(entry)

        dirs_list.sort(key=lambda s: s.lower())
        files_list.sort(key=lambda s: s.lower())

        for dir_name in dirs_list:
            entry_rel = os.path.join(rel_path, dir_name) if rel_path else dir_name
            node = parent_node.add(Text(f"📁 {dir_name}", style="bold cyan"),
                                   data={"path": entry_rel, "is_dir": True})
            self._add_directory(node, os.path.join(abs_path, dir_name), entry_rel)

        for file_name in files_list:
            entry_rel = os.path.join(rel_path, file_name) if rel_path else file_name
            is_locked, holder = self.lock_manager.is_locked(entry_rel)
            if is_locked:
                label = Text(f"  {file_name} 🔒 {holder}", style="bold red")
            else:
                label = Text(f"  {file_name}", style="white")
            parent_node.add_leaf(label, data={"path": entry_rel, "is_dir": False})

    def should_ignore(self, name: str) -> bool:
        if name.startswith("."):
            return True
        if name in ("__pycache__", "node_modules", ".venv", "venv"):
            return True
        if name.endswith(".pyc"):
            return True
        return False
