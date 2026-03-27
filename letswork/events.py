from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

class EventType(str, Enum):
    CONNECTION = "connection"
    DISCONNECTION = "disconnection"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_LOCK = "file_lock"
    FILE_UNLOCK = "file_unlock"
    CHAT_MESSAGE = "chat_message"
    FILE_TREE_REQUEST = "file_tree_request"
    ERROR = "error"

@dataclass
class Event:
    timestamp: datetime
    event_type: EventType
    user_id: str
    data: dict = field(default_factory=dict)
    message: str = ""

class EventLog:
    def __init__(self):
        self._events: list[Event] = []
        self._listeners: list[Callable] = []

    def emit(self, event_type: EventType, user_id: str, data: dict | None = None) -> Event:
        if data is None:
            data = {}
        
        message = self.format_event(event_type, user_id, data)
        event = Event(
            timestamp=datetime.now(),
            event_type=event_type,
            user_id=user_id,
            data=data,
            message=message
        )
        self._events.append(event)
        
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass
                
        return event

    def on_event(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def get_recent(self, count: int = 50) -> list[Event]:
        return self._events[-count:]

    def format_event(self, event_type: EventType, user_id: str, data: dict | None = None) -> str:
        if data is None:
            data = {}
            
        time = datetime.now().strftime("%H:%M:%S")
        
        if event_type == EventType.CONNECTION:
            return f"[{time}] ✅ {user_id} connected"
        elif event_type == EventType.DISCONNECTION:
            return f"[{time}] ❌ {user_id} disconnected"
        elif event_type == EventType.FILE_READ:
            return f"[{time}] 📖 {user_id} read {data.get('path', '?')}"
        elif event_type == EventType.FILE_WRITE:
            return f"[{time}] ✏️  {user_id} wrote {data.get('path', '?')}"
        elif event_type == EventType.FILE_LOCK:
            return f"[{time}] 🔒 {user_id} locked {data.get('path', '?')}"
        elif event_type == EventType.FILE_UNLOCK:
            return f"[{time}] 🔓 {user_id} unlocked {data.get('path', '?')}"
        elif event_type == EventType.CHAT_MESSAGE:
            return f"[{time}] 💬 {user_id}: {data.get('message', '')}"
        elif event_type == EventType.FILE_TREE_REQUEST:
            return f"[{time}] 📁 {user_id} viewed file tree"
            
        return f"[{time}] {event_type} event by {user_id}"
