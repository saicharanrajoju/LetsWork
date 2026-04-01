"""Standalone LetsWork chat window — simple Textual UI."""
import argparse
import threading

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input

from letswork.remote_client import RemoteClient


class ChatApp(App):
    TITLE = "LetsWork Chat"
    CSS = """
    Screen { layout: vertical; }
    #messages {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    #chat-input { height: 3; dock: bottom; }
    """
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, url: str, token: str, role: str, name: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.token = token
        self.role = role.lower()
        self.display_name = name
        self._client = RemoteClient(url, token)
        self._connected = False
        self._last_index = 0
        self._poll_in_progress = False

    @property
    def role_label(self) -> str:
        return "HOST" if self.role == "host" else "GUEST"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="messages", markup=True, wrap=True)
        yield Input(
            placeholder=f"[{self.role_label}] {self.display_name}: type here and press Enter",
            id="chat-input",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"[{self.role_label}] {self.display_name}"
        log = self.query_one("#messages", RichLog)
        log.write("[bold]─── LetsWork Chat ──────────────────────────────────────────[/bold]")
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self) -> None:
        self._connected = self._client.connect()
        if self._connected:
            self._client.register_name(self.display_name)

        def _update():
            log = self.query_one("#messages", RichLog)
            if self._connected:
                log.write("[dim]connected — start chatting[/dim]")
                self.set_interval(1.0, self._poll)
            else:
                log.write("[bold red]❌ Failed to connect to MCP server[/bold red]")

        self.call_from_thread(_update)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or not self._connected:
            return
        msg = f"[{self.role_label}] {self.display_name}: {text}"
        event.input.value = ""
        threading.Thread(target=self._send, args=(msg,), daemon=True).start()

    def _send(self, message: str) -> None:
        self._client.send_message(message)

    def _poll(self) -> None:
        if self._poll_in_progress:
            return
        self._poll_in_progress = True
        threading.Thread(target=self._fetch_events, daemon=True).start()

    def _fetch_events(self) -> None:
        try:
            result = self._client.get_events(self._last_index)
            if not result or result == "no_new_events" or result.startswith("Error"):
                return

            lines = result.strip().split("\n")
            new_index = self._last_index
            chat_lines = []

            for line in lines:
                if line.startswith("__INDEX__:"):
                    try:
                        new_index = int(line.split(":", 1)[1])
                    except (ValueError, IndexError):
                        pass
                elif "💬" in line:
                    # Format: "[HH:MM:SS] 💬 user_id: [ROLE] Name: text"
                    try:
                        after_emoji = line.split("💬 ", 1)[1]    # "user_id: [ROLE] Name: text"
                        content = after_emoji.split(": ", 1)[1]   # "[ROLE] Name: text"
                        if content.startswith("[HOST]"):
                            chat_lines.append(f"  [bold blue]{content}[/bold blue]")
                        elif content.startswith("[GUEST]"):
                            chat_lines.append(f"  [bold green]{content}[/bold green]")
                        else:
                            chat_lines.append(f"  {content}")
                    except (IndexError, ValueError):
                        pass

            def _update():
                self._last_index = new_index
                if chat_lines:
                    log = self.query_one("#messages", RichLog)
                    for line in chat_lines:
                        log.write(line)

            self.call_from_thread(_update)
        except Exception:
            pass
        finally:
            self._poll_in_progress = False

    def action_quit(self) -> None:
        self._client.disconnect()
        self.exit()


def main() -> None:
    parser = argparse.ArgumentParser(description="LetsWork Chat Window")
    parser.add_argument("--url", required=True, help="MCP server URL")
    parser.add_argument("--token", required=True, help="Session token")
    parser.add_argument("--role", required=True, choices=["host", "guest"])
    parser.add_argument("--name", required=True, help="Your display name")
    args = parser.parse_args()
    ChatApp(url=args.url, token=args.token, role=args.role, name=args.name).run()


if __name__ == "__main__":
    main()
