import os
import pytest
import letswork.server as server_module
from letswork.server import (
    safe_resolve,
    list_files,
    read_file,
    write_file,
    lock_file,
    unlock_file,
    get_status,
    send_message,
    get_events,
)

TOKEN = "test-token"
USER = "test-user"


@pytest.fixture(autouse=True, scope="function")
def setup_server(tmp_path):
    server_module.project_root = str(tmp_path)
    server_module.session_token = TOKEN
    server_module.lock_manager._locks = {}
    server_module.token_to_user.clear()
    server_module.register_user(TOKEN, USER)
    server_module.event_log._events.clear()
    server_module.approval_queue = None

    (tmp_path / "hello.txt").write_text("hello world")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested content")

    yield


# ── safe_resolve ──────────────────────────────────────────────────────────────

def test_safe_resolve_valid_path():
    result = safe_resolve("hello.txt", server_module.project_root)
    assert result == os.path.join(server_module.project_root, "hello.txt")


def test_safe_resolve_traversal_blocked():
    with pytest.raises(ValueError) as exc_info:
        safe_resolve("../../etc/passwd", server_module.project_root)
    assert "Access denied" in str(exc_info.value)


# ── auth ──────────────────────────────────────────────────────────────────────

def test_list_files_bad_token():
    with pytest.raises(ValueError) as exc_info:
        list_files(token="wrong")
    assert "Unauthorized" in str(exc_info.value)


def test_read_file_bad_token():
    with pytest.raises(ValueError) as exc_info:
        read_file(token="wrong", path="hello.txt")
    assert "Unauthorized" in str(exc_info.value)


# ── list_files ────────────────────────────────────────────────────────────────

def test_list_files_returns_entries():
    result = list_files(TOKEN)
    assert "hello.txt" in result
    assert "subdir" in result


def test_list_files_shows_lock_status():
    server_module.lock_manager.acquire_lock("hello.txt", "alice")
    result = list_files(TOKEN)
    assert "hello.txt" in result
    assert "locked by alice" in result


# ── read_file ─────────────────────────────────────────────────────────────────

def test_read_file_success():
    result = read_file(TOKEN, "hello.txt")
    assert result == "hello world"


def test_read_file_not_found():
    with pytest.raises(ValueError) as exc_info:
        read_file(TOKEN, "missing.txt")
    assert "File not found" in str(exc_info.value)


def test_read_file_too_large(tmp_path):
    big_file = tmp_path / "big.txt"
    big_file.write_text("x" * 1_048_577)
    with pytest.raises(ValueError) as exc_info:
        read_file(TOKEN, "big.txt")
    assert "too large" in str(exc_info.value)


# ── write_file ────────────────────────────────────────────────────────────────

def test_write_file_with_auto_lock(tmp_path):
    write_file(TOKEN, "new.txt", "new content")
    assert (tmp_path / "new.txt").read_text() == "new content"
    assert server_module.lock_manager.is_locked("new.txt") == (True, USER)


def test_write_file_rejected_when_locked_by_other():
    server_module.lock_manager.acquire_lock("hello.txt", "other-user")
    with pytest.raises(ValueError) as exc_info:
        write_file(TOKEN, "hello.txt", "changed")
    assert "locked by other-user" in str(exc_info.value)


# ── lock_file ─────────────────────────────────────────────────────────────────

def test_lock_file_success():
    lock_file(TOKEN, "hello.txt")
    assert server_module.lock_manager.is_locked("hello.txt") == (True, USER)


def test_lock_file_conflict():
    server_module.lock_manager.acquire_lock("hello.txt", "other-user")
    with pytest.raises(ValueError) as exc_info:
        lock_file(TOKEN, "hello.txt")
    assert "already locked by other-user" in str(exc_info.value)


# ── unlock_file ───────────────────────────────────────────────────────────────

def test_unlock_file_success():
    server_module.lock_manager.acquire_lock("hello.txt", USER)
    unlock_file(TOKEN, "hello.txt")
    assert server_module.lock_manager.is_locked("hello.txt") == (False, None)


def test_unlock_file_not_owner():
    server_module.lock_manager.acquire_lock("hello.txt", "other-user")
    with pytest.raises(ValueError) as exc_info:
        unlock_file(TOKEN, "hello.txt")
    assert "you do not hold this lock" in str(exc_info.value)


# ── get_status ────────────────────────────────────────────────────────────────

def test_get_status_no_locks():
    result = get_status(TOKEN)
    assert "Active locks: none" in result


def test_get_status_with_locks():
    server_module.lock_manager.acquire_lock("hello.txt", "alice")
    result = get_status(TOKEN)
    assert "hello.txt" in result
    assert "locked by alice" in result


# ── send_message ──────────────────────────────────────────────────────────────

def test_send_message_success():
    result = send_message(TOKEN, "hello team")
    assert "Message sent" in result
    events = server_module.event_log._events
    assert any("hello team" in e.data.get("message", "") for e in events)


def test_send_message_empty_rejected():
    with pytest.raises(ValueError) as exc_info:
        send_message(TOKEN, "   ")
    assert "empty" in str(exc_info.value).lower()


# ── get_events ────────────────────────────────────────────────────────────────

def test_get_events_no_new():
    result = get_events(TOKEN, since_index=0)
    assert result == "no_new_events"


def test_get_events_returns_events():
    server_module.event_log.emit(server_module.EventType.CHAT_MESSAGE, USER, {"message": "hi"})
    result = get_events(TOKEN, since_index=0)
    assert "hi" in result
    assert "__INDEX__:1" in result


def test_get_events_since_index():
    server_module.event_log.emit(server_module.EventType.FILE_READ, USER, {"path": "a.txt"})
    server_module.event_log.emit(server_module.EventType.FILE_READ, USER, {"path": "b.txt"})
    result = get_events(TOKEN, since_index=1)
    assert "b.txt" in result
    assert "a.txt" not in result
