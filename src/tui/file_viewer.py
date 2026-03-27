import os
from textual.widgets import Static, TextArea
from textual.containers import Vertical, ScrollableContainer
from textual.app import ComposeResult
from rich.syntax import Syntax

class FileViewerWidget(Vertical):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_file = ""
        self.project_root = ""
        self.edit_mode = False
        self._current_content = ""

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(Static("📄 File Viewer\n\nSelect a file to view", id="viewer-display"), id="viewer-scroll")
        yield TextArea("", id="viewer-editor", show_line_numbers=True, tab_behavior="indent")

    def on_mount(self) -> None:
        editor = self.query_one("#viewer-editor", TextArea)
        editor.display = False

    def load_file(self, file_path: str, project_root: str) -> None:
        self.project_root = project_root
        abs_path = os.path.join(project_root, file_path)
        if not os.path.isfile(abs_path):
            display = self.query_one("#viewer-display", Static)
            display.update(f"📄 File not found: {file_path}")
            return
        if os.path.getsize(abs_path) > 1_048_576:
            display = self.query_one("#viewer-display", Static)
            display.update(f"📄 File too large: {file_path}")
            return
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                contents = f.read()
            self._current_content = contents
            self.current_file = file_path
            language = self._get_language(file_path)
            syntax = Syntax(contents, language, theme="monokai", line_numbers=True, word_wrap=True)
            display = self.query_one("#viewer-display", Static)
            display.update(syntax)
            display.styles.height = "auto"
            # If in edit mode, also update editor
            if self.edit_mode:
                editor = self.query_one("#viewer-editor", TextArea)
                editor.text = contents
        except UnicodeDecodeError:
            display = self.query_one("#viewer-display", Static)
            display.update(f"📄 Cannot display binary file: {file_path}")
        except Exception as e:
            display = self.query_one("#viewer-display", Static)
            display.update(f"📄 Error: {e}")

    def toggle_edit(self) -> None:
        if not self.current_file:
            return
        self.edit_mode = not self.edit_mode
        editor = self.query_one("#viewer-editor", TextArea)
        if self.edit_mode:
            # Set language BEFORE setting text so highlighter applies
            language = self._get_textarea_language(self.current_file)
            if language:
                editor.language = language
            else:
                editor.language = None
            # Set theme
            editor.theme = "monokai"
            # Set line numbers
            editor.show_line_numbers = True
            # NOW set the text content
            editor.text = self._current_content
            # Set indent
            editor.indent_width = 4
            # Show editor, hide viewer
            scroll = self.query_one("#viewer-scroll")
            scroll.display = False
            editor.display = True
            editor.focus()
        else:
            editor.display = False
            scroll = self.query_one("#viewer-scroll")
            scroll.display = True
            # Reload file to show current syntax-highlighted view
            self.load_file(self.current_file, self.project_root)

    def get_editor_content(self) -> str:
        """Returns the current text in the editor."""
        editor = self.query_one("#viewer-editor", TextArea)
        return editor.text

    def clear_viewer(self) -> None:
        self.current_file = ""
        self._current_content = ""
        self.edit_mode = False
        display = self.query_one("#viewer-display", Static)
        display.update("📄 File Viewer\n\nSelect a file to view")
        scroll = self.query_one("#viewer-scroll")
        scroll.display = True
        editor = self.query_one("#viewer-editor", TextArea)
        editor.display = False

    def _get_textarea_language(self, file_path: str) -> str | None:
        """Map file extension to TextArea language (subset of supported languages)."""
        ext = os.path.splitext(file_path)[1].lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": None,
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".toml": "toml",
            ".sh": "bash",
            ".sql": "sql",
            ".rs": "rust",
            ".go": "go",
            ".rb": None,
        }
        return mapping.get(ext, None)

    def _get_language(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".py":
            return "python"
        elif ext == ".js":
            return "javascript"
        elif ext == ".ts":
            return "typescript"
        elif ext == ".html":
            return "html"
        elif ext == ".css":
            return "css"
        elif ext == ".json":
            return "json"
        elif ext == ".md":
            return "markdown"
        elif ext in [".yml", ".yaml"]:
            return "yaml"
        elif ext == ".toml":
            return "toml"
        elif ext == ".sh":
            return "bash"
        elif ext == ".sql":
            return "sql"
        elif ext == ".rs":
            return "rust"
        elif ext == ".go":
            return "go"
        elif ext == ".rb":
            return "ruby"
        elif ext == ".txt":
            return "text"
        else:
            return "text"
