"""Diagnóstico de inicialização e verificação de ambiente do sistema."""
import os
import sys
import time
import shutil
import socket
import zipfile
import tarfile
import tempfile
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Optional, List, Callable
from src.utils.logger import log_info, log_error, log_warning

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
    """Procura pelo FFmpeg no PATH do sistema, diretório da aplicação e pasta local do usuário."""
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    user_bin = os.path.join(os.path.expanduser("~"), ".nexusfetch", "bin")

    is_win = (os.name == "nt")
    exe_name = "ffmpeg.exe" if is_win else "ffmpeg"

    possible_local_paths = [
        os.path.join(app_dir, exe_name),
        os.path.join(app_dir, "bin", exe_name),
        os.path.join(app_dir, "_internal", "bin", exe_name),
        os.path.join(user_bin, exe_name),
    ]
    
    ffmpeg_exe = None
    for p in possible_local_paths:
        if os.path.isfile(p):
            ffmpeg_exe = p
            # Adiciona ao PATH da sessão atual para subprocessos e yt-dlp
            bin_dir = os.path.dirname(p)
            if bin_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
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

def install_ffmpeg_auto(on_progress: Optional[Callable[[float, str], None]] = None) -> tuple[bool, str]:
    """
    Baixa e instala automaticamente uma versão estática do FFmpeg sem necessidade de intervenção do usuário.
    Extrai apenas ffmpeg e ffprobe na pasta do usuário ~/.nexusfetch/bin/ e configura o PATH.
    """
    target_bin = os.path.join(os.path.expanduser("~"), ".nexusfetch", "bin")
    os.makedirs(target_bin, exist_ok=True)

    is_win = (os.name == "nt")

    if is_win:
        download_urls = [
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
            "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        ]
    else:
        download_urls = [
            "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
        ]

    temp_archive = os.path.join(tempfile.gettempdir(), "nexus_ffmpeg_download.tmp")

    last_error = ""
    for url in download_urls:
        try:
            if on_progress:
                on_progress(2.0, "Conectando ao servidor oficial do FFmpeg...")

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (NexusFetch Automator)"}
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                total_bytes = int(resp.getheader("Content-Length", 0))
                downloaded = 0
                start_time = time.time()
                last_update = 0.0

                with open(temp_archive, "wb") as f_out:
                    chunk_size = 1024 * 512  # 512 KB
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if on_progress and (now - last_update > 0.15 or downloaded == total_bytes):
                            last_update = now
                            elapsed = max(0.01, now - start_time)
                            speed_mb = (downloaded / (1024 * 1024)) / elapsed
                            pct = (downloaded / total_bytes * 85.0) if total_bytes > 0 else 50.0
                            dl_mb = downloaded / (1024 * 1024)
                            tot_mb = total_bytes / (1024 * 1024) if total_bytes > 0 else 0
                            msg = f"Baixando FFmpeg... {dl_mb:.1f} MB / {tot_mb:.1f} MB ({speed_mb:.1f} MB/s)"
                            on_progress(pct, msg)

            if on_progress:
                on_progress(90.0, "Extraindo binários do FFmpeg...")

            # Extração dos binários
            if is_win:
                with zipfile.ZipFile(temp_archive, "r") as zf:
                    for member in zf.namelist():
                        bname = os.path.basename(member).lower()
                        if bname in ("ffmpeg.exe", "ffprobe.exe"):
                            out_path = os.path.join(target_bin, os.path.basename(member))
                            with zf.open(member) as src, open(out_path, "wb") as dst:
                                shutil.copyfileobj(src, dst)
            else:
                with tarfile.open(temp_archive, "r:*") as tf:
                    for member in tf.getmembers():
                        bname = os.path.basename(member.name)
                        if bname in ("ffmpeg", "ffprobe"):
                            f = tf.extractfile(member)
                            if f:
                                out_path = os.path.join(target_bin, bname)
                                with open(out_path, "wb") as dst:
                                    shutil.copyfileobj(f, dst)
                                os.chmod(out_path, 0o755)

            # Limpa o arquivo temporário baixado
            if os.path.exists(temp_archive):
                try:
                    os.remove(temp_archive)
                except Exception:
                    pass

            # Adiciona ao PATH e verifica
            if target_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = target_bin + os.pathsep + os.environ.get("PATH", "")

            ok, path, ver = find_ffmpeg()
            if ok:
                if on_progress:
                    on_progress(100.0, "FFmpeg instalado e configurado com sucesso!")
                log_info(f"FFmpeg instalado com sucesso automaticamente em: {path}")
                return True, f"FFmpeg instalado com sucesso em {path}!"
            else:
                last_error = "Arquivos extraídos, mas não foi possível validar execução do binário."

        except Exception as e:
            last_error = str(e)
            log_error(f"Falha ao baixar/instalar FFmpeg a partir de {url}: {e}")
            if os.path.exists(temp_archive):
                try:
                    os.remove(temp_archive)
                except Exception:
                    pass

    return False, f"Falha na instalação automática do FFmpeg: {last_error}"

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
