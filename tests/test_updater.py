"""Testes unitários para o módulo de atualização do yt-dlp e do aplicativo."""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from src.utils.updater import (
    get_installed_ytdlp_version,
    get_current_binary_name,
    check_and_update_ytdlp,
    check_app_update,
    is_update_ready,
    apply_pending_update_if_any
)

def test_get_current_binary_name():
    name = get_current_binary_name()
    if sys.platform == "win32":
        assert name == "NexusFetch.exe"
    else:
        assert name == "NexusFetch"

def test_get_installed_ytdlp_version():
    ver = get_installed_ytdlp_version()
    assert isinstance(ver, str)
    assert len(ver) > 0
    assert ver != "0.0.0"

def test_check_and_update_ytdlp_already_latest():
    current_ver = get_installed_ytdlp_version()
    mock_pypi = {
        "info": {"version": current_ver},
        "urls": []
    }
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_pypi).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        updated, msg = check_and_update_ytdlp()
        assert updated is False
        assert "já está atualizado" in msg

def test_check_app_update_no_commits():
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([]).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        info = check_app_update()
        assert info is None

def test_is_update_ready_false_when_empty():
    assert is_update_ready() is False

def test_apply_pending_update_noop_on_updated_flag():
    old_argv = sys.argv
    try:
        sys.argv = ["main.py", "--updated"]
        assert apply_pending_update_if_any() is False
    finally:
        sys.argv = old_argv
