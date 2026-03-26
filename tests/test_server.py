import os
import pytest
import src.server as server_module
from src.server import safe_resolve, list_files, read_file, write_file, lock_file, unlock_file, get_status


@pytest.fixture(autouse=True, scope="function")
def setup_server(tmp_path):
    server_module.project_root = str(tmp_path)
    server_module.session_token = "test-token"
    server_module.lock_manager._locks = {}
    
    (tmp_path / "hello.txt").write_text("hello world")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested content")
    
    yield


def test_safe_resolve_valid_path():
    result = safe_resolve("hello.txt", server_module.project_root)
    assert result == os.path.join(server_module.project_root, "hello.txt")


def test_safe_resolve_traversal_blocked():
    with pytest.raises(ValueError) as exc_info:
        safe_resolve("../../etc/passwd", server_module.project_root)
    assert "Access denied" in str(exc_info.value)


def test_list_files_returns_entries():
    result = list_files()
    assert "hello.txt" in result
    assert "subdir" in result


def test_list_files_shows_lock_status():
    server_module.lock_manager.acquire_lock("hello.txt", "alice")
    result = list_files()
    assert "hello.txt" in result
    assert "locked by alice" in result


def test_read_file_success():
    result = read_file("hello.txt")
    assert result == "hello world"


def test_read_file_not_found():
    with pytest.raises(ValueError) as exc_info:
        read_file("missing.txt")
    assert "File not found" in str(exc_info.value)


def test_read_file_too_large(tmp_path):
    big_file = tmp_path / "big.txt"
    big_file.write_text("x" * 1_048_577)
    with pytest.raises(ValueError) as exc_info:
        read_file("big.txt")
    assert "too large" in str(exc_info.value)


def test_write_file_with_auto_lock(tmp_path):
    write_file("new.txt", "new content", "alice")
    assert (tmp_path / "new.txt").read_text() == "new content"
    assert server_module.lock_manager.is_locked("new.txt") == (True, "alice")


def test_write_file_rejected_when_locked_by_other():
    server_module.lock_manager.acquire_lock("hello.txt", "bob")
    with pytest.raises(ValueError) as exc_info:
        write_file("hello.txt", "changed", "alice")
    assert "locked by bob" in str(exc_info.value)


def test_lock_file_success():
    lock_file("hello.txt", "alice")
    assert server_module.lock_manager.is_locked("hello.txt") == (True, "alice")


def test_lock_file_conflict():
    server_module.lock_manager.acquire_lock("hello.txt", "bob")
    with pytest.raises(ValueError) as exc_info:
        lock_file("hello.txt", "alice")
    assert "already locked by bob" in str(exc_info.value)


def test_unlock_file_success():
    server_module.lock_manager.acquire_lock("hello.txt", "alice")
    unlock_file("hello.txt", "alice")
    assert server_module.lock_manager.is_locked("hello.txt") == (False, None)


def test_unlock_file_not_owner():
    server_module.lock_manager.acquire_lock("hello.txt", "bob")
    with pytest.raises(ValueError) as exc_info:
        unlock_file("hello.txt", "alice")
    assert "you do not hold this lock" in str(exc_info.value)


def test_get_status_no_locks():
    result = get_status()
    assert "Active locks: none" in result


def test_get_status_with_locks():
    server_module.lock_manager.acquire_lock("hello.txt", "alice")
    result = get_status()
    assert "hello.txt" in result
    assert "locked by alice" in result
