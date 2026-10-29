"""Diagnóstico de inicialização e verificação de ambiente do sistema."""
import os
import sys
import shutil
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class DiagnosticResult:
    ffmpeg_available: bool
    ffmpeg_path: Optional[str]
    ffmpeg_version: Optional[str]
    internet_available: bool
    write_permission: bool
    missing_critical: List[str]
    warnings: List[str]

    @property
    def is_all_ok(self) -> bool:
        return self.ffmpeg_available and self.internet_available and self.write_permission

def find_ffmpeg() -> tuple[bool, Optional[str], Optional[str]]:
    """Procura pelo FFmpeg no PATH do sistema e em diretórios locais."""
    # 1. Checa diretório da aplicação (útil para distribuição portátil)
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    possible_local_paths = [
        os.path.join(app_dir, "ffmpeg.exe"),
        os.path.join(app_dir, "bin", "ffmpeg.exe"),
        os.path.join(app_dir, "_internal", "bin", "ffmpeg.exe"),
    ]
    
    ffmpeg_exe = None
    for p in possible_local_paths:
        if os.path.isfile(p):
            ffmpeg_exe = p
            break
            
    # 2. Se não achou local, checa PATH global do sistema
    if not ffmpeg_exe:
        ffmpeg_exe = shutil.which("ffmpeg")

    if not ffmpeg_exe:
        return False, None, None

    # Tenta executar para pegar a versão
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        proc = subprocess.run(
            [ffmpeg_exe, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            startupinfo=startupinfo
        )
        if proc.returncode == 0:
            first_line = proc.stdout.splitlines()[0] if proc.stdout else "Disponível"
            return True, ffmpeg_exe, first_line
    except Exception:
        pass

    return True, ffmpeg_exe, "Instalado"

def check_internet(timeout: float = 2.0) -> bool:
    """Verifica conexão ativa de internet via socket rápido."""
    hosts = [("1.1.1.1", 53), ("8.8.8.8", 53)]
    for host, port in hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return True
        except Exception:
            continue
    return False

def check_write_permission(directory: str) -> bool:
    """Valida se o usuário tem permissão de escrita no diretório alvo."""
    try:
        os.makedirs(directory, exist_ok=True)
        test_file = os.path.join(directory, ".nexus_test_perm")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False

def run_startup_diagnostics(download_dir: Optional[str] = None) -> DiagnosticResult:
    """Executa a verificação completa do ambiente e retorna o status detalhado."""
    from src.config import DEFAULT_DOWNLOAD_DIR
    target_dir = download_dir or DEFAULT_DOWNLOAD_DIR

    ffmpeg_ok, ffmpeg_path, ffmpeg_ver = find_ffmpeg()
    internet_ok = check_internet()
    write_ok = check_write_permission(target_dir)

    missing_critical: List[str] = []
    warnings: List[str] = []

    if not ffmpeg_ok:
        missing_critical.append("FFmpeg não foi detectado no sistema (necessário para MP3 e mesclagem de vídeo em alta resolução).")
    
    if not internet_ok:
        warnings.append("Sem conexão com a internet detectada no momento.")

    if not write_ok:
        missing_critical.append(f"Sem permissão de gravação na pasta: {target_dir}")

    return DiagnosticResult(
        ffmpeg_available=ffmpeg_ok,
        ffmpeg_path=ffmpeg_path,
        ffmpeg_version=ffmpeg_ver,
        internet_available=internet_ok,
        write_permission=write_ok,
        missing_critical=missing_critical,
        warnings=warnings
    )
