import os
from mcp.server.fastmcp import FastMCP
from src.filelock import LockManager
from src.auth import validate_token

app = FastMCP("letswork")
lock_manager = LockManager()
session_token: str = ""
project_root: str = ""


def check_auth(provided_token: str) -> bool:
    """Validates a provided token against the session token. Raises an error if invalid."""
    if not validate_token(provided_token, session_token):
        raise ValueError("Unauthorized: invalid token")
    return True


@app.tool()
def list_files(path: str = ".") -> str:
    resolved_path = os.path.join(project_root, path)
    resolved_path = os.path.abspath(resolved_path)
    
    if not resolved_path.startswith(os.path.abspath(project_root)):
        raise ValueError("Access denied: path outside project directory")
        
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
def read_file(path: str) -> str:
    resolved_path = os.path.join(project_root, path)
    resolved_path = os.path.abspath(resolved_path)
    
    if not resolved_path.startswith(os.path.abspath(project_root)):
        raise ValueError("Access denied: path outside project directory")
        
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
def write_file(path: str, content: str, user_id: str) -> str:
    resolved_path = os.path.join(project_root, path)
    resolved_path = os.path.abspath(resolved_path)
    
    if not resolved_path.startswith(os.path.abspath(project_root)):
        raise ValueError("Access denied: path outside project directory")
        
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))
    
    is_locked, holder = lock_manager.is_locked(relative_path)
    if is_locked and holder != user_id:
        raise ValueError(f"File is locked by {holder}. Cannot write.")
        
    if not is_locked:
        lock_manager.acquire_lock(relative_path, user_id)
        
    if len(content.encode("utf-8")) > 1_048_576:
        raise ValueError("Content too large: exceeds 1MB limit")
        
    dir_name = os.path.dirname(resolved_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
        
    with open(resolved_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return f"Successfully wrote to {path} (locked by {user_id})"


@app.tool()
def lock_file(path: str, user_id: str) -> str:
    resolved_path = os.path.join(project_root, path)
    resolved_path = os.path.abspath(resolved_path)
    
    if not resolved_path.startswith(os.path.abspath(project_root)):
        raise ValueError("Access denied: path outside project directory")
        
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))
    
    is_locked, holder = lock_manager.is_locked(relative_path)
    if is_locked and holder != user_id:
        raise ValueError(f"File is already locked by {holder}")
        
    if is_locked and holder == user_id:
        return f"File {path} is already locked by you"
        
    lock_manager.acquire_lock(relative_path, user_id)
    return f"Locked {path} for {user_id}"


@app.tool()
def unlock_file(path: str, user_id: str) -> str:
    resolved_path = os.path.join(project_root, path)
    resolved_path = os.path.abspath(resolved_path)
    
    if not resolved_path.startswith(os.path.abspath(project_root)):
        raise ValueError("Access denied: path outside project directory")
        
    relative_path = os.path.relpath(resolved_path, os.path.abspath(project_root))
    
    if not lock_manager.release_lock(relative_path, user_id):
        raise ValueError(f"Cannot unlock {path}: you do not hold this lock")
        
    return f"Unlocked {path}"


@app.tool()
def get_status() -> str:
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
