import os
from textual.widgets import Tree

class FileTreeWidget(Tree):
    def __init__(self, project_root: str, lock_manager, remote_client=None, **kwargs):
        self.project_root = project_root
        self.lock_manager = lock_manager
        self.remote_client = remote_client
        super().__init__("📁 Project", **kwargs)

    def on_mount(self) -> None:
        self.build_tree()

    def build_tree(self) -> None:
        self.root.remove_children()
        if self.remote_client is not None:
            self._build_remote_tree()
        else:
            self._add_directory(self.root, self.project_root, "")

    def _parse_listing_line(self, line: str) -> tuple[str, bool, str | None]:
        """Parse one line from list_files output.
        Returns (path, is_dir, lock_holder_or_None)"""
        line = line.strip()
        if line.startswith("[dir] "):
            path = line[6:].strip()
            return (path, True, None)
        if line.startswith("[file] "):
            rest = line[7:].strip()
            if " [locked by " in rest:
                parts = rest.split(" [locked by ", 1)
                path = parts[0]
                holder = parts[1].rstrip("]")
                return (path, False, holder)
            return (rest, False, None)
        return ("", False, None)

    def _build_remote_tree(self) -> None:
        listing = self.remote_client.list_files(".")
        if not listing or listing.startswith("Error") or listing == "Directory is empty":
            self.root.add_leaf("(empty or error)")
            return
        self._populate_node(self.root, listing)

    def _populate_node(self, node, listing: str) -> None:
        dirs_list = []
        files_list = []

        for line in listing.splitlines():
            path, is_dir, holder = self._parse_listing_line(line)
            if not path:
                continue
            name = path.split("/")[-1] if "/" in path else path.split("\\")[-1] if "\\" in path else path
            if is_dir:
                dirs_list.append((name, path))
            else:
                files_list.append((name, path, holder))

        dirs_list.sort(key=lambda x: x[0].lower())
        files_list.sort(key=lambda x: x[0].lower())

        for dir_name, full_rel_path in dirs_list:
            dir_node = node.add(f"📁 {dir_name}", data={"path": full_rel_path, "is_dir": True})
            sub_listing = self.remote_client.list_files(full_rel_path)
            if sub_listing and not sub_listing.startswith("Error") and sub_listing != "Directory is empty":
                self._populate_node(dir_node, sub_listing)

        for file_name, full_rel_path, holder in files_list:
            if holder:
                label = f"📄 {file_name} 🔒 {holder}"
            else:
                label = f"📄 {file_name}"
            node.add_leaf(label, data={"path": full_rel_path, "is_dir": False})

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
            label = f"📁 {dir_name}"
            node = parent_node.add(label, data={"path": entry_rel, "is_dir": True})
            self._add_directory(node, os.path.join(abs_path, dir_name), entry_rel)

        for file_name in files_list:
            entry_rel = os.path.join(rel_path, file_name) if rel_path else file_name
            is_locked, holder = self.lock_manager.is_locked(entry_rel)
            if is_locked:
                label = f"📄 {file_name} 🔒 {holder}"
            else:
                label = f"📄 {file_name}"
            parent_node.add_leaf(label, data={"path": entry_rel, "is_dir": False})

    def should_ignore(self, name: str) -> bool:
        if name.startswith("."):
            return True
        if name == "__pycache__":
            return True
        if name == "node_modules":
            return True
        if name == ".venv" or name == "venv":
            return True
        if name.endswith(".pyc"):
            return True
        return False

    def refresh_tree(self) -> None:
        self.build_tree()
        self.root.expand()
