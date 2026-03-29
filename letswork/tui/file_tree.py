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
        self.refresh_tree()

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
        """Fetch all remote data in background thread, then rebuild tree on main thread."""
        try:
            data = self._fetch_tree_data(".")
        except Exception:
            data = None

        def _rebuild():
            self.root.remove_children()
            if data is None:
                self.root.add_leaf("(empty or error)")
            else:
                self._populate_from_data(self.root, data)
            self.root.expand()
            self._refresh_in_progress = False

        self.call_from_thread(_rebuild)

    def _fetch_tree_data(self, path: str) -> list:
        """Recursively fetch directory structure. Runs in background thread."""
        listing = self.remote_client.list_files(path)
        if not listing or listing.startswith("Error") or listing == "Directory is empty":
            return []

        dirs_list = []
        files_list = []
        for line in listing.splitlines():
            p, is_dir, holder = self._parse_listing_line(line)
            if not p:
                continue
            name = p.split("/")[-1] if "/" in p else p.split("\\")[-1] if "\\" in p else p
            if is_dir:
                dirs_list.append((name, p))
            else:
                files_list.append((name, p, holder))

        dirs_list.sort(key=lambda x: x[0].lower())
        files_list.sort(key=lambda x: x[0].lower())

        result = []
        for dir_name, full_rel_path in dirs_list:
            children = self._fetch_tree_data(full_rel_path)
            result.append({"name": dir_name, "path": full_rel_path, "is_dir": True, "children": children})
        for file_name, full_rel_path, holder in files_list:
            result.append({"name": file_name, "path": full_rel_path, "is_dir": False, "holder": holder})
        return result

    def _populate_from_data(self, node, items: list) -> None:
        """Build tree nodes from pre-fetched data. Must run on main thread."""
        for item in items:
            if item["is_dir"]:
                dir_node = node.add(Text(f"📁 {item['name']}", style="bold cyan"),
                                    data={"path": item["path"], "is_dir": True})
                self._populate_from_data(dir_node, item["children"])
            else:
                holder = item.get("holder")
                if holder:
                    label = Text(f"  {item['name']} 🔒 {holder}", style="bold red")
                else:
                    label = Text(f"  {item['name']}", style="white")
                node.add_leaf(label, data={"path": item["path"], "is_dir": False})

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
