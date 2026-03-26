from src.filelock import LockManager


def test_acquire_lock_success():
    """Acquiring a lock on an unlocked file returns True."""
    lm = LockManager()
    assert lm.acquire_lock("file.py", "user_a") is True


def test_acquire_lock_same_user():
    """Acquiring a lock the user already holds returns True."""
    lm = LockManager()
    lm.acquire_lock("file.py", "user_a")
    assert lm.acquire_lock("file.py", "user_a") is True


def test_acquire_lock_conflict():
    """Acquiring a lock held by another user returns False."""
    lm = LockManager()
    lm.acquire_lock("file.py", "user_a")
    assert lm.acquire_lock("file.py", "user_b") is False


def test_release_lock_success():
    """Owner can release their own lock."""
    lm = LockManager()
    lm.acquire_lock("file.py", "user_a")
    assert lm.release_lock("file.py", "user_a") is True


def test_release_lock_not_owner():
    """Non-owner cannot release someone else's lock."""
    lm = LockManager()
    lm.acquire_lock("file.py", "user_a")
    assert lm.release_lock("file.py", "user_b") is False


def test_is_locked():
    """is_locked returns correct status and holder."""
    lm = LockManager()
    assert lm.is_locked("file.py") == (False, None)
    lm.acquire_lock("file.py", "user_a")
    assert lm.is_locked("file.py") == (True, "user_a")


def test_release_all():
    """release_all clears every lock."""
    lm = LockManager()
    lm.acquire_lock("a.py", "user_a")
    lm.acquire_lock("b.py", "user_b")
    lm.release_all()
    assert lm.get_locks() == {}
