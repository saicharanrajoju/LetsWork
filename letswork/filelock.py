from datetime import datetime


class LockManager:
    """Manages file-level locks for collaborative editing. Maps file paths to user IDs."""

    def __init__(self):
        # Internal: dict[path -> (user_id, acquired_at)]
        self._locks: dict[str, tuple[str, datetime]] = {}

    def acquire_lock(self, path: str, user_id: str) -> bool:
        """Acquire a lock on a file for the given user."""
        if path not in self._locks:
            self._locks[path] = (user_id, datetime.now())
            return True
        if self._locks[path][0] == user_id:
            return True
        return False

    def release_lock(self, path: str, user_id: str) -> bool:
        """Release a lock only if the user is the current owner."""
        if path not in self._locks:
            return False
        if self._locks[path][0] != user_id:
            return False
        del self._locks[path]
        return True

    def get_locks(self) -> dict[str, str]:
        """Return a copy of all active locks as {path: user_id}."""
        return {path: entry[0] for path, entry in self._locks.items()}

    def is_locked(self, path: str) -> tuple[bool, str | None]:
        """Check if a file is locked. Returns (is_locked, holder_user_id)."""
        if path in self._locks:
            return (True, self._locks[path][0])
        return (False, None)

    def release_all(self) -> None:
        """Release all locks. Used when session ends."""
        self._locks.clear()

    def release_expired(self, max_age_seconds: int = 1800) -> list[str]:
        """Release locks older than max_age_seconds. Returns list of released paths."""
        now = datetime.now()
        expired = [
            path for path, (_, acquired_at) in self._locks.items()
            if (now - acquired_at).total_seconds() > max_age_seconds
        ]
        for path in expired:
            del self._locks[path]
        return expired

    def force_release(self, path: str) -> bool:
        """Force-release a lock regardless of owner. Returns True if a lock existed."""
        if path not in self._locks:
            return False
        del self._locks[path]
        return True
