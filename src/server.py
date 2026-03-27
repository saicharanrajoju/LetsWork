import os
from mcp.server.fastmcp import FastMCP
from src.filelock import LockManager
from src.auth import validate_token
from src.events import EventLog, EventType
from src.approval import ApprovalQueue

app = FastMCP("letswork")
lock_manager = LockManager()
event_log = EventLog()
approval_queue: ApprovalQueue | None = None
session_token: str = ""
project_root: str = ""
token_to_user: dict[str, str] = {}


def check_auth(provided_token: str) -> bool:
    """Validates a provided token against the session token. Returns False if invalid."""
    return validate_token(provided_token, session_token)


def register_user(token: str, user_id: str) -> None:
    """Associate a token with a user_id."""
    token_to_user[token] = user_id


def get_user(token: str) -> str:
    """Resolve a token to its user_id. Returns 'unknown' if not registered."""
    return token_to_user.get(token, "unknown")


def safe_resolve(path: str, root: str) -> str:
    abs_root = os.path.abspath(root)
    resolved = os.path.abspath(os.path.join(abs_root, path))
    if not resolved.startswith(abs_root + os.sep) and resolved != abs_root:
        raise ValueError("Access denied: path outside project directory")
    return resolved

@app.tool()
def list_files(token: str, path: str = ".") -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    resolved_path = safe_resolve(path, project_root)
    event_log.emit(EventType.FILE_TREE_REQUEST, "host", {"path": path})
        
    if not os.path.exists(resolved_path):
        raise ValueError(f"Path not found: {path}")
        
    if not os.path.isdir(resolved_path):
        raise ValueError(f"Not a directory: {path}")
        
    listing = os.listdir(resolved_path)
    listing.sort()
    
    if not listing:
        return "Directory is empty"
        
    result_lines = []
    for entry in listing:
        full_entry_path = os.path.join(resolved_path, entry)
        relative_path = os.path.relpath(full_entry_path, project_root)
        entry_type = "[dir]" if os.path.isdir(full_entry_path) else "[file]"
        
        is_locked, holder = lock_manager.is_locked(relative_path)
        lock_info = f" [locked by {holder}]" if is_locked else ""
        
        result_lines.append(f"{entry_type} {relative_path}{lock_info}")
        
    return "\n".join(result_lines)


@app.tool()
def read_file(token: str, path: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    resolved_path = safe_resolve(path, project_root)
    event_log.emit(EventType.FILE_READ, "host", {"path": path})
        
    if not os.path.exists(resolved_path):
        raise ValueError(f"File not found: {path}")
        
    if not os.path.isfile(resolved_path):
        raise ValueError(f"Not a file: {path}")
        
    if os.path.getsize(resolved_path) > 1_048_576:
        raise ValueError(f"File too large: {path} exceeds 1MB limit")
        
    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        raise ValueError(f"Cannot read {path}: not a text file")


@app.tool()
def write_file(token: str, path: str, content: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    resolved_path = safe_resolve(path, project_root)
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))

    is_locked, holder = lock_manager.is_locked(relative_path)
    if is_locked and holder != user_id:
        raise ValueError(f"File is locked by {holder}. Cannot write.")
        
    if not is_locked:
        lock_manager.acquire_lock(relative_path, user_id)
        
    if len(content.encode("utf-8")) > 1_048_576:
        raise ValueError("Content too large: exceeds 1MB limit")

    if approval_queue is not None:
        change = approval_queue.submit(user_id, path, content)
        event_log.emit(EventType.FILE_WRITE, user_id, {"path": path, "status": "pending_approval", "change_id": change.id})
        return f"Change submitted for approval (ID: {change.id}). Waiting for host to approve."
    else:
        # No approval queue (standalone mode) — write directly
        parent = os.path.dirname(resolved_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(resolved_path, "w", encoding="utf-8") as f:
            f.write(content)
        event_log.emit(EventType.FILE_WRITE, user_id, {"path": path})
        return f"Successfully wrote to {path} (locked by {user_id})"


@app.tool()
def lock_file(token: str, path: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    resolved_path = safe_resolve(path, project_root)
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))
    
    is_locked, holder = lock_manager.is_locked(relative_path)
    if is_locked and holder != user_id:
        raise ValueError(f"File is already locked by {holder}")
        
    if is_locked and holder == user_id:
        return f"File {path} is already locked by you"
        
    lock_manager.acquire_lock(relative_path, user_id)
    event_log.emit(EventType.FILE_LOCK, user_id, {"path": path})
    return f"Locked {path} for {user_id}"


@app.tool()
def unlock_file(token: str, path: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    resolved_path = safe_resolve(path, project_root)
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))
    
    if not lock_manager.release_lock(relative_path, user_id):
        raise ValueError(f"Cannot unlock {path}: you do not hold this lock")
        
    event_log.emit(EventType.FILE_UNLOCK, user_id, {"path": path})
    return f"Unlocked {path}"


@app.tool()
def get_status(token: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    status_lines = []
    status_lines.append(f"Project root: {project_root}")
    
    locks = lock_manager.get_locks()
    if not locks:
        status_lines.append("Active locks: none")
    else:
        status_lines.append("Active locks:")
        for path, user_id in sorted(locks.items()):
            status_lines.append(f"  {path} — locked by {user_id}")
            
    return "\n".join(status_lines)


@app.tool()
def send_message(token: str, message: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    if not message.strip():
        raise ValueError("Message cannot be empty")
    event_log.emit(EventType.CHAT_MESSAGE, user_id, {"message": message})
    return f"Message sent by {user_id}"


@app.tool()
def get_events(token: str, since_index: int = 0) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    if since_index >= len(event_log._events):
        return "no_new_events"
    
    new_events = event_log._events[since_index:]
    result_lines = []
    for event in new_events:
        result_lines.append(event.message)
        
    result_lines.append(f"__INDEX__:{len(event_log._events)}")
    return "\n".join(result_lines)


@app.tool()
def get_pending_changes(token: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    if approval_queue is None:
        return "No approval system active"
        
    pending = approval_queue.get_pending()
    if not pending:
        return "No pending changes"
        
    result_lines = []
    for change in pending:
        result_lines.append(f"Change {change.id}: {change.path} by {change.user_id}")
        result_lines.append(approval_queue.get_diff(change.id))
        result_lines.append("")
        
    return "\n".join(result_lines)


@app.tool()
def approve_change(token: str, change_id: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    if approval_queue is None:
        raise ValueError("Approval system not active")
    if not approval_queue.approve(change_id):
        raise ValueError(f"Change {change_id} not found")
    return f"Change {change_id} approved and written to disk"


@app.tool()
def reject_change(token: str, change_id: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    if approval_queue is None:
        raise ValueError("Approval system not active")
    if not approval_queue.reject(change_id):
        raise ValueError(f"Change {change_id} not found")
    return f"Change {change_id} rejected"
