"""Notificações nativas do Sistema Operacional (Windows, Linux e macOS) sem dependências externas."""
import os
import sys
import shutil
import threading
import subprocess
from typing import Optional

from src.utils.logger import log_warning
from src.utils.settings import get_setting


def _ps_escape(text: str) -> str:
    return text.replace("'", "''").replace("\n", " ").replace("\r", " ")


def _send_windows_notification(title: str, message: str) -> bool:
    ps_title = _ps_escape(title)
    ps_msg = _ps_escape(message)
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$ni = New-Object System.Windows.Forms.NotifyIcon; "
        "$ni.Icon = [System.Drawing.SystemIcons]::Information; "
        "$ni.Visible = $true; "
        f"$ni.ShowBalloonTip(4000, '{ps_title}', '{ps_msg}', [System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Milliseconds 4500; "
        "$ni.Dispose()"
    )
    ps_exe = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
    )
    if not os.path.exists(ps_exe):
        ps_exe = "powershell.exe"

    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def _send_linux_notification(title: str, message: str) -> bool:
    notify_bin = shutil.which("notify-send")
    if not notify_bin:
        return False
    subprocess.Popen(
        [notify_bin, "-a", "Nexus Fetch", "-i", "dialog-information", title, message],
        start_new_session=True,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def _send_macos_notification(title: str, message: str) -> bool:
    osa_bin = shutil.which("osascript")
    if not osa_bin:
        return False
    safe_title = title.replace('"', '\\"')
    safe_msg = message.replace('"', '\\"')
    subprocess.Popen(
        [osa_bin, "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
        start_new_session=True,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def send_native_notification(title: str, message: str, enabled: Optional[bool] = None) -> bool:
    """Envia uma notificação nativa do SO respeitando a preferência notifications_enabled."""
    if enabled is None:
        enabled = bool(get_setting("notifications_enabled", True))
    if not enabled:
        return False

    try:
        if sys.platform == "win32":
            return _send_windows_notification(title, message)
        if sys.platform == "darwin":
            return _send_macos_notification(title, message)
        return _send_linux_notification(title, message)
    except Exception as e:
        log_warning(f"Falha ao enviar notificação nativa: {e}")
        return False


def notify_async(title: str, message: str) -> None:
    """Dispara notificação nativa em thread daemon sem bloquear a interface."""
    threading.Thread(
        target=send_native_notification,
        args=(title, message),
        daemon=True,
    ).start()
