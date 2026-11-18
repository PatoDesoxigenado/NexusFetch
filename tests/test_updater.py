"""Testes unitários para o módulo de atualização do yt-dlp e do aplicativo."""
import os
import sys
import json
import time
import shutil
import subprocess
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
    install_app_update_in_place,
    spawn_update_progress_popup,
    _build_windows_progress_popup_script,
    _build_linux_progress_popup_script,
    _cleanup_update_artifacts,
    _build_clean_subprocess_env,
    _is_valid_binary_header,
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


def test_install_app_update_in_place_keeps_old_and_confirms(tmp_path):
    bin_name = get_current_binary_name()
    magic = b"MZ\x90\x00" if bin_name.endswith(".exe") else b"\x7fELF"

    target_exe = tmp_path / bin_name
    ready_exe = tmp_path / f"{bin_name}.ready"
    target_exe.write_bytes(magic + b"OLD_VERSION")
    ready_exe.write_bytes(magic + b"NEW_VERSION")

    statuses = []
    ok, result_path, old_path = install_app_update_in_place(
        ready_dest=str(ready_exe),
        target_exe=str(target_exe),
        on_status=lambda m: statuses.append(m),
    )
    assert ok is True
    assert result_path == str(target_exe)
    assert os.path.exists(target_exe)
    assert target_exe.read_bytes() == magic + b"NEW_VERSION"
    assert os.path.exists(old_path)
    assert open(old_path, "rb").read() == magic + b"OLD_VERSION"
    assert not ready_exe.exists()
    assert any("✓ Atualização concluída!" in s and str(target_exe) in s for s in statuses)


def test_install_app_update_in_place_rollback_on_move_failure(tmp_path):
    bin_name = get_current_binary_name()
    magic = b"MZ\x90\x00" if bin_name.endswith(".exe") else b"\x7fELF"

    target_exe = tmp_path / bin_name
    ready_exe = tmp_path / f"{bin_name}.ready"
    target_exe.write_bytes(magic + b"SAFE_ORIGINAL")
    ready_exe.write_bytes(magic + b"BROKEN_MOVE")

    with patch("src.utils.updater.shutil.move", side_effect=OSError("Disk error")):
        ok, msg, old_path = install_app_update_in_place(str(ready_exe), str(target_exe))
        assert ok is False
        assert old_path == ""
        # Rollback deve ter restaurado o executável original intacto!
        assert target_exe.exists()
        assert target_exe.read_bytes() == magic + b"SAFE_ORIGINAL"


def test_apply_app_update_rejects_corrupt_ready_file(tmp_path):
    update_dir = tmp_path / "update"
    update_dir.mkdir()
    bin_name = get_current_binary_name()
    ready_file = update_dir / f"{bin_name}.ready"
    ready_file.write_bytes(b"<html>not a binary</html>")

    with patch("src.utils.updater.UPDATE_DIR", str(update_dir)):
        assert apply_app_update_and_restart() is False
        assert not ready_file.exists()


def test_apply_app_update_swaps_in_place_and_spawns_new_binary_directly(tmp_path):
    update_dir = tmp_path / "update"
    user_dir = tmp_path / "user"
    app_dir = tmp_path / "app"
    update_dir.mkdir()
    user_dir.mkdir()
    app_dir.mkdir()

    bin_name = get_current_binary_name()
    magic = b"MZ\x90\x00" if bin_name.endswith(".exe") else b"\x7fELF"
    target_exe = app_dir / bin_name
    ready_file = update_dir / f"{bin_name}.ready"
    target_exe.write_bytes(magic + b"OLD_BIN")
    ready_file.write_bytes(magic + b"NEW_BIN")

    mock_proc = MagicMock()
    mock_proc.pid = 4242

    with (
        patch("src.utils.updater.UPDATE_DIR", str(update_dir)),
        patch("src.utils.updater.USER_DATA_DIR", str(user_dir)),
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "executable", str(target_exe)),
        patch("src.utils.updater.subprocess.Popen", return_value=mock_proc) as mock_popen,
        patch("src.utils.updater.os._exit") as mock_exit,
        patch.dict(os.environ, {"_MEIPASS2": r"C:\Temp\_MEI999"}, clear=False),
    ):
        apply_app_update_and_restart()
        assert mock_popen.call_count >= 1
        # A última chamada de Popen é o novo executável direto (a anterior é o pop-up visual)
        cmd, kwargs = mock_popen.call_args[0][0], mock_popen.call_args[1]
        assert cmd[0] == str(target_exe)
        assert "--updated" in cmd
        assert any(arg.startswith("--cleanup-old=") for arg in cmd)
        assert "_MEIPASS2" not in kwargs["env"]
        assert target_exe.read_bytes() == magic + b"NEW_BIN"
        assert (app_dir / f"{bin_name}.old").read_bytes() == magic + b"OLD_BIN"
        assert mock_exit.call_args[0] == (0,)


def test_popup_scripts_content():
    win_s = _build_windows_progress_popup_script(r"C:\Apps\O'Brien\NexusFetch.exe.old")
    assert "Atualização em andamento, aguarde..." in win_s
    assert "Marquee" in win_s
    assert "O''Brien" in win_s

    lin_s = _build_linux_progress_popup_script("/opt/nexus/NexusFetch.old")
    assert "Atualização em andamento, aguarde..." in lin_s
    assert "--pulsate" in lin_s
    assert "/opt/nexus/NexusFetch.old" in lin_s


def test_apply_pending_update_never_exits_on_startup(tmp_path):
    """Garante que apply_pending_update_if_any NUNCA fecha o app na inicialização (zero boot-loop)."""
    update_dir = tmp_path / "update"
    update_dir.mkdir()
    bin_name = get_current_binary_name()
    magic = b"MZ\x90\x00" if bin_name.endswith(".exe") else b"\x7fELF"
    ready_file = update_dir / f"{bin_name}.ready"
    ready_file.write_bytes(magic + b"\x00" * (21 * 1024 * 1024))

    with (
        patch("src.utils.updater.UPDATE_DIR", str(update_dir)),
        patch.object(sys, "frozen", True, create=True),
        patch("src.utils.updater.os._exit") as mock_exit,
    ):
        assert apply_pending_update_if_any() is False
        assert not mock_exit.called


def test_live_running_exe_in_place_update_and_cleanup(tmp_path):
    """
    Teste real de integração no Windows:
    1. Inicia um executável real em execução (janela/processo aberto).
    2. Enquanto o processo antigo está ABERTO, executa install_app_update_in_place
       (renomeando o atual em execução para .old e colocando o novo no lugar).
    3. Inicia o novo executável diretamente e encerra o antigo.
    4. Executa _cleanup_update_artifacts e comprova que o .old é apagado e o novo permanece.
    """
    if sys.platform != "win32":
        pytest.skip("Teste de processo PE em execução específico para Windows")

    ping_src = r"C:\Windows\System32\ping.exe"
    target_exe = tmp_path / "NexusFetch.exe"
    ready_exe = tmp_path / "NexusFetch.exe.ready"
    shutil.copy2(ping_src, target_exe)
    shutil.copy2(ping_src, ready_exe)

    old_proc = subprocess.Popen(
        [str(target_exe), "127.0.0.1", "-n", "10"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.3)
        assert old_proc.poll() is None, "Processo antigo deveria estar em execução"

        statuses = []
        ok, new_path, old_path = install_app_update_in_place(
            ready_dest=str(ready_exe),
            target_exe=str(target_exe),
            on_status=lambda s: statuses.append(s),
        )
        assert ok is True
        assert os.path.exists(new_path)
        assert os.path.exists(old_path)
        assert not ready_exe.exists()

        # Agora encerra o processo antigo e limpa o .old
        old_proc.terminate()
        old_proc.wait(timeout=5)

        _cleanup_update_artifacts(extra_old_path=old_path, max_retries=10, retry_delay=0.2)
        assert not os.path.exists(old_path), "O arquivo temporário .old deveria ter sido apagado"
        assert os.path.exists(target_exe), "O novo executável deve continuar intacto"
    finally:
        if old_proc.poll() is None:
            old_proc.kill()
