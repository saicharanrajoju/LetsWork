import pytest
import subprocess
from unittest import mock
from src.tunnel import start_tunnel, stop_tunnel


@mock.patch("shutil.which", return_value=None)
def test_start_tunnel_cloudflared_not_installed(mock_which):
    """Verify start_tunnel raises RuntimeError when cloudflared is not found"""
    with pytest.raises(RuntimeError) as exc_info:
        start_tunnel(8080)
    assert "cloudflared is not installed" in str(exc_info.value)


@mock.patch("subprocess.Popen")
@mock.patch("shutil.which", return_value="/usr/bin/cloudflared")
def test_start_tunnel_returns_url(mock_which, mock_popen):
    """Verify start_tunnel parses and returns the HTTPS URL from stderr"""
    mock_process = mock.MagicMock()
    mock_process.stderr.readline.side_effect = [
        b"2024-01-01 INFO Starting tunnel\n",
        b"2024-01-01 INFO https://abc123-test.trycloudflare.com\n"
    ]
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process
    
    url, process = start_tunnel(8080)
    
    assert url == "https://abc123-test.trycloudflare.com"
    assert process is mock_process


@mock.patch("subprocess.Popen")
@mock.patch("shutil.which", return_value="/usr/bin/cloudflared")
def test_start_tunnel_timeout(mock_which, mock_popen):
    """Verify start_tunnel raises RuntimeError when no URL is found after 30 lines"""
    mock_process = mock.MagicMock()
    mock_process.stderr.readline.side_effect = [b"no url here\n"] * 30
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process
    
    with pytest.raises(RuntimeError) as exc_info:
        start_tunnel(8080)
        
    assert "could not find tunnel URL" in str(exc_info.value)
    mock_process.terminate.assert_called_once()


def test_stop_tunnel_graceful():
    """Verify stop_tunnel calls terminate and wait"""
    mock_process = mock.MagicMock()
    
    stop_tunnel(mock_process)
    
    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called_once_with(timeout=5)


def test_stop_tunnel_force_kill():
    """Verify stop_tunnel calls kill when wait times out"""
    mock_process = mock.MagicMock()
    mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="cloudflared", timeout=5)
    
    stop_tunnel(mock_process)
    
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()
