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
    apply_pending_update_if_any,
    apply_app_update_and_restart,
    _build_clean_subprocess_env,
    _is_valid_binary_header,
    _build_windows_updater_script,
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


def test_build_clean_subprocess_env_strips_pyinstaller_vars():
    sep = ";" if sys.platform == "win32" else ":"
    fake_mei = r"C:\Users\Test\AppData\Local\Temp\_MEI12345" if sys.platform == "win32" else "/tmp/_MEI12345"
    safe_dir = r"C:\Windows\System32" if sys.platform == "win32" else "/usr/bin"
    fake_env = {
        "_MEIPASS": fake_mei,
        "_MEIPASS2": fake_mei,
        "_PYI_APPLICATION_HOME_DIR": fake_mei,
        "_PYI_SPLASH_IPC": "1234",
        "TCL_LIBRARY": os.path.join(fake_mei, "_tcl_data"),
        "TK_LIBRARY": os.path.join(fake_mei, "_tk_data"),
        "PYTHONHOME": fake_mei,
        "PYTHONPATH": fake_mei,
        "PATH": f"{fake_mei}{sep}{safe_dir}",
        "SYSTEMROOT": r"C:\Windows",
    }
    with patch.dict(os.environ, fake_env, clear=True):
        with patch.object(sys, "_MEIPASS", fake_mei, create=True):
            cleaned = _build_clean_subprocess_env()
            for bad_key in ("_MEIPASS", "_MEIPASS2", "_PYI_APPLICATION_HOME_DIR", "_PYI_SPLASH_IPC", "TCL_LIBRARY", "TK_LIBRARY", "PYTHONHOME", "PYTHONPATH"):
                assert bad_key not in cleaned
            assert fake_mei not in cleaned["PATH"]
            assert safe_dir in cleaned["PATH"]
            assert cleaned["SYSTEMROOT"] == r"C:\Windows"


def test_is_valid_binary_header(tmp_path):
    exe_file = tmp_path / "NexusFetch.exe"
    exe_file.write_bytes(b"MZ\x90\x00dummy")
    assert _is_valid_binary_header(str(exe_file), "NexusFetch.exe") is True
    assert _is_valid_binary_header(str(exe_file), "NexusFetch") is False

    elf_file = tmp_path / "NexusFetch"
    elf_file.write_bytes(b"\x7fELF\x02\x01\x01\x00")
    assert _is_valid_binary_header(str(elf_file), "NexusFetch") is True
    assert _is_valid_binary_header(str(elf_file), "NexusFetch.exe") is False

    html_file = tmp_path / "broken.exe"
    html_file.write_bytes(b"<!DOCTYPE html>")
    assert _is_valid_binary_header(str(html_file), "NexusFetch.exe") is False


def test_build_windows_updater_script_escapes_and_guards():
    script = _build_windows_updater_script(
        ready_dest=r"C:\Users\O'Brien\.nexusfetch\update\NexusFetch.exe.ready",
        target_exe=r"C:\Apps\Nexus Fetch\NexusFetch.exe",
        child_pid=1111,
        parent_pid=2222,
        log_file=r"C:\Users\O'Brien\.nexusfetch\logs\updater.log",
    )
    assert "O''Brien" in script
    assert "$ChildPid = 1111" in script
    assert "$ParentPid = 2222" in script
    assert "NexusFetch*" in script
    assert "$BackupExe" in script
    assert "Start-Process -FilePath $TargetExe -ArgumentList '--updated'" in script


def test_apply_app_update_rejects_corrupt_ready_file(tmp_path):
    update_dir = tmp_path / "update"
    update_dir.mkdir()
    bin_name = get_current_binary_name()
    ready_file = update_dir / f"{bin_name}.ready"
    ready_file.write_bytes(b"<html>not a binary</html>")

    with patch("src.utils.updater.UPDATE_DIR", str(update_dir)):
        assert apply_app_update_and_restart() is False
        assert not ready_file.exists()


def test_apply_app_update_spawns_clean_powershell_on_windows(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Teste específico de spawn Windows")

    update_dir = tmp_path / "update"
    user_dir = tmp_path / "user"
    log_dir = tmp_path / "logs"
    update_dir.mkdir()
    user_dir.mkdir()
    log_dir.mkdir()

    ready_file = update_dir / "NexusFetch.exe.ready"
    ready_file.write_bytes(b"MZ\x90\x00" + b"\x00" * 1024)

    with (
        patch("src.utils.updater.UPDATE_DIR", str(update_dir)),
        patch("src.utils.updater.USER_DATA_DIR", str(user_dir)),
        patch("src.utils.updater.LOG_DIR", str(log_dir)),
        patch("src.utils.updater.subprocess.Popen") as mock_popen,
        patch("src.utils.updater.os._exit") as mock_exit,
        patch.dict(os.environ, {"_MEIPASS2": r"C:\Temp\_MEI999", "SYSTEMROOT": r"C:\Windows"}, clear=False),
    ):
        apply_app_update_and_restart()
        assert mock_popen.called
        cmd, kwargs = mock_popen.call_args[0][0], mock_popen.call_args[1]
        assert cmd[0].lower().endswith("powershell.exe")
        assert "-ExecutionPolicy" in cmd
        assert "Bypass" in cmd
        assert "_MEIPASS2" not in kwargs["env"]
        assert mock_exit.called_with(0) or mock_exit.call_args[0] == (0,)
