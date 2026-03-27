from datetime import datetime
from textual.containers import Vertical
from textual.widgets import RichLog, Input
from textual.app import ComposeResult
from letswork.events import EventLog, EventType, Event

class ChatWidget(Vertical):
    def __init__(self, event_log: EventLog, user_id: str = "host", remote_client=None, **kwargs):
        super().__init__(**kwargs)
        self.event_log = event_log
        self.user_id = user_id
        self.remote_client = remote_client

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-messages", markup=True, highlight=True, wrap=True)
        yield Input(placeholder="Type a message and press Enter...", id="chat-input")

    def on_mount(self) -> None:
        chat_log = self.query_one("#chat-messages", RichLog)
        chat_log.write("[bold cyan]💬 Chat[/bold cyan]")
        self.event_log.on_event(self._on_event)
        
        for event in self.event_log.get_recent():
            if event.event_type == EventType.CHAT_MESSAGE:
                chat_log.write(event.message)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return

        if self.remote_client:
            # Guest mode — send via MCP
            self.remote_client.send_message(message)
            # Immediate local feedback while server echo catches up
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.query_one("#chat-messages", RichLog).write(
                f"[{timestamp}] 💬 {self.user_id}: {message}"
            )
        else:
            # Host mode — emit to shared in-memory event_log
            self.event_log.emit(EventType.CHAT_MESSAGE, self.user_id, {"message": message})

        event.input.value = ""

    def _on_event(self, event: Event) -> None:
        if event.event_type != EventType.CHAT_MESSAGE:
            return
            
        try:
            chat_log = self.query_one("#chat-messages", RichLog)
            chat_log.write(event.message)
        except Exception:
            pass
