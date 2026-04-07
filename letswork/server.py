import os
from mcp.server.fastmcp import FastMCP
from letswork.filelock import LockManager
from letswork.auth import validate_token
from letswork.events import EventLog, EventType
from letswork.approval import ApprovalQueue

app = FastMCP("letswork")
lock_manager = LockManager()
event_log = EventLog()
approval_queue: ApprovalQueue | None = None
valid_tokens: set[str] = set()
project_root: str = ""
token_to_user: dict[str, str] = {}


def check_auth(provided_token: str) -> bool:
    """Validates a provided token against all registered tokens."""
    return any(validate_token(provided_token, t) for t in valid_tokens)


def register_user(token: str, user_id: str) -> None:
    """Associate a token with a user_id and mark it as valid."""
    token_to_user[token] = user_id
    valid_tokens.add(token)


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
def ping(token: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    event_log.emit(EventType.PING, user_id, {})
    return f"pong — connected to {project_root} as {user_id}"


@app.tool()
def get_notifications(token: str) -> str:
    """Returns a summary of what needs attention right now."""
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    lines = []

    if approval_queue is not None:
        pending = approval_queue.get_pending()
        if pending:
            lines.append(f"⏳ {len(pending)} change(s) pending approval:")
            for change in pending:
                lines.append(f"   • [{change.id}] {change.path} — submitted by {change.user_id}")
            if user_id == "host":
                lines.append("   → use approve_change or reject_change to action them")
            else:
                lines.append("   → waiting for host to review")
        else:
            lines.append("✅ No pending changes")

    locks = lock_manager.get_locks()
    if locks:
        lines.append(f"🔒 {len(locks)} active lock(s):")
        for path, holder in sorted(locks.items()):
            lines.append(f"   • {path} — locked by {holder}")

    if not lines:
        lines.append("✅ All clear — nothing needs attention")

    return "\n".join(lines)


@app.tool()
def list_files(token: str, path: str = ".", recursive: bool = False) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    try:
        resolved_path = safe_resolve(path, project_root)
    except ValueError:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Path traversal blocked: {path}"})
        raise
    event_log.emit(EventType.FILE_TREE_REQUEST, user_id, {"path": path})

    if not os.path.exists(resolved_path):
        raise ValueError(f"Path not found: {path}")
    if not os.path.isdir(resolved_path):
        raise ValueError(f"Not a directory: {path}")

    result_lines = []

    if recursive:
        for root_dir, dirs, files in os.walk(resolved_path):
            # Skip hidden dirs and common noise
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".venv", "venv"))
            for fname in sorted(files):
                if fname.startswith("."):
                    continue
                full = os.path.join(root_dir, fname)
                rel = os.path.relpath(full, project_root)
                is_locked, holder = lock_manager.is_locked(rel)
                lock_info = f" [locked by {holder}]" if is_locked else ""
                result_lines.append(f"[file] {rel}{lock_info}")
    else:
        listing = sorted(os.listdir(resolved_path))
        for entry in listing:
            full_entry_path = os.path.join(resolved_path, entry)
            relative_path = os.path.relpath(full_entry_path, project_root)
            entry_type = "[dir]" if os.path.isdir(full_entry_path) else "[file]"
            is_locked, holder = lock_manager.is_locked(relative_path)
            lock_info = f" [locked by {holder}]" if is_locked else ""
            result_lines.append(f"{entry_type} {relative_path}{lock_info}")

    return "\n".join(result_lines) if result_lines else "Directory is empty"


@app.tool()
def read_file(token: str, path: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    try:
        resolved_path = safe_resolve(path, project_root)
    except ValueError:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Path traversal blocked: {path}"})
        raise
    event_log.emit(EventType.FILE_READ, user_id, {"path": path})

    if not os.path.exists(resolved_path):
        event_log.emit(EventType.ERROR, user_id, {"error": f"File not found: {path}"})
        raise ValueError(f"File not found: {path}")

    if not os.path.isfile(resolved_path):
        raise ValueError(f"Not a file: {path}")

    if os.path.getsize(resolved_path) > 1_048_576:
        event_log.emit(EventType.ERROR, user_id, {"error": f"File too large: {path}"})
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
    try:
        resolved_path = safe_resolve(path, project_root)
    except ValueError:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Path traversal blocked: {path}"})
        raise
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))

    is_locked, holder = lock_manager.is_locked(relative_path)
    if is_locked and holder != user_id:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Write rejected, locked by {holder}: {path}"})
        raise ValueError(f"File is locked by {holder}. Cannot write.")

    if not is_locked:
        lock_manager.acquire_lock(relative_path, user_id)

    if len(content.encode("utf-8")) > 1_048_576:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Write rejected, content too large: {path}"})
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
    try:
        resolved_path = safe_resolve(path, project_root)
    except ValueError:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Path traversal blocked: {path}"})
        raise
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))

    is_locked, holder = lock_manager.is_locked(relative_path)
    if is_locked and holder != user_id:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Lock conflict, held by {holder}: {path}"})
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
    try:
        resolved_path = safe_resolve(path, project_root)
    except ValueError:
        event_log.emit(EventType.ERROR, user_id, {"error": f"Path traversal blocked: {path}"})
        raise
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))

    if not lock_manager.release_lock(relative_path, user_id):
        event_log.emit(EventType.ERROR, user_id, {"error": f"Unlock failed, wrong owner: {path}"})
        raise ValueError(f"Cannot unlock {path}: you do not hold this lock")
        
    event_log.emit(EventType.FILE_UNLOCK, user_id, {"path": path})
    return f"Unlocked {path}"


@app.tool()
def get_status(token: str) -> str:
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    status_lines = []
    status_lines.append(f"Project root: {project_root}")

    users = list(set(token_to_user.values()))
    status_lines.append(f"Connected users: {', '.join(users) if users else 'none'}")

    locks = lock_manager.get_locks()
    if not locks:
        status_lines.append("Active locks: none")
    else:
        status_lines.append("Active locks:")
        for path, uid in sorted(locks.items()):
            status_lines.append(f"  {path} — locked by {uid}")

    if approval_queue is not None:
        pending = approval_queue.get_pending()
        if pending:
            status_lines.append(f"Pending approvals: {len(pending)}")
            for change in pending:
                status_lines.append(f"  [{change.id}] {change.path} by {change.user_id}")

    return "\n".join(status_lines)


@app.tool()
def my_pending_changes(token: str) -> str:
    """Show only your own pending changes awaiting approval."""
    if not check_auth(token):
        raise ValueError("Unauthorized: invalid token")
    user_id = get_user(token)
    if approval_queue is None:
        return "No approval system active"
    pending = [c for c in approval_queue.get_pending() if c.user_id == user_id]
    if not pending:
        return "You have no pending changes"
    lines = [f"{len(pending)} change(s) pending approval:"]
    for change in pending:
        lines.append(f"  [{change.id}] {change.path}")
    return "\n".join(lines)


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
