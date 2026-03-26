class LockManager:
    """Manages file-level locks for collaborative editing. Maps file paths to user IDs."""

    def __init__(self):
        self._locks: dict[str, str] = {}

    def acquire_lock(self, path: str, user_id: str) -> bool:
        """Acquire a lock on a file for the given user."""
        if path not in self._locks:
            self._locks[path] = user_id
            return True
        if self._locks[path] == user_id:
            return True
        return False

    def release_lock(self, path: str, user_id: str) -> bool:
        """Release a lock only if the user is the current owner."""
        if path not in self._locks:
            return False
        if self._locks[path] != user_id:
            return False
        del self._locks[path]
        return True

    def get_locks(self) -> dict[str, str]:
        """Return a copy of all active locks."""
        return self._locks.copy()

    def is_locked(self, path: str) -> tuple[bool, str | None]:
        """Check if a file is locked. Returns (is_locked, holder_user_id)."""
        if path in self._locks:
            return (True, self._locks[path])
        return (False, None)

    def release_all(self) -> None:
        """Release all locks. Used when session ends."""
        self._locks.clear()
