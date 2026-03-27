import os
from textual.widgets import Tree

class FileTreeWidget(Tree):
    def __init__(self, project_root: str, lock_manager, **kwargs):
        self.project_root = project_root
        self.lock_manager = lock_manager
        super().__init__("📁 Project", **kwargs)

    def on_mount(self) -> None:
        self.build_tree()

    def build_tree(self) -> None:
        self.root.remove_children()
        self._add_directory(self.root, self.project_root, "")

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
