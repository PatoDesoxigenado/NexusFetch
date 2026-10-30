"""Módulo de atualização automática do motor do YouTube (yt-dlp) e do próprio executável."""
import os
import sys
import json
import time
import shutil
import zipfile
import tempfile
import subprocess
import urllib.request
from typing import Optional, Tuple, Dict, Callable
from src.utils.logger import log_info, log_error, log_warning

USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".nexusfetch")
PACKAGES_DIR = os.path.join(USER_DATA_DIR, "packages")
UPDATE_DIR = os.path.join(USER_DATA_DIR, "update")
GITHUB_REPO = "PatoDesoxigenado/NexusFetch"

def get_current_binary_name() -> str:
    """Retorna o nome do executável esperado de acordo com a plataforma."""
    return "NexusFetch.exe" if sys.platform == "win32" else "NexusFetch"

# ------------------------------------------------------------------------------
# 1. ATUALIZAÇÃO AUTOMÁTICA DO YT-DLP
# ------------------------------------------------------------------------------

def get_installed_ytdlp_version() -> str:
    """Obtém a versão atualmente importada do yt-dlp."""
    try:
        import yt_dlp.version
        return str(yt_dlp.version.__version__)
    except Exception:
        return "0.0.0"

def check_and_update_ytdlp(on_status: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
    """
    Verifica no PyPI se há uma versão mais nova do yt-dlp.
    Se houver, baixa a wheel (.whl), extrai em ~/.nexusfetch/packages e carrega no sys.path.
    """
    try:
        current_ver = get_installed_ytdlp_version()
        log_info(f"Checando atualizacao do yt-dlp (versao instalada: {current_ver})...")

        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"User-Agent": "NexusFetch-AutoUpdater"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_ver = data.get("info", {}).get("version")
        if not latest_ver:
            return False, "Não foi possível obter a versão mais recente do yt-dlp."

        # Se já estiver na versão mais nova ou superior
        if latest_ver <= current_ver:
            log_info(f"yt-dlp ja esta atualizado ({current_ver}).")
            return False, f"yt-dlp já está atualizado ({current_ver})."

        if on_status:
            on_status(f"Nova versão do motor do YouTube encontrada (v{latest_ver}). Baixando...")

        # Localiza o arquivo .whl universal
        whl_url = None
        for u in data.get("urls", []):
            fname = u.get("filename", "")
            if fname.endswith("-py2.py3-none-any.whl") or fname.endswith("-py3-none-any.whl"):
                whl_url = u.get("url")
                break

        if not whl_url:
            return False, "Arquivo wheel do yt-dlp não localizado no PyPI."

        os.makedirs(PACKAGES_DIR, exist_ok=True)
        temp_whl = os.path.join(tempfile.gettempdir(), f"ytdlp_update_{latest_ver}.whl")

        req_whl = urllib.request.Request(whl_url, headers={"User-Agent": "NexusFetch-AutoUpdater"})
        with urllib.request.urlopen(req_whl, timeout=30) as whl_resp, open(temp_whl, "wb") as f_out:
            shutil.copyfileobj(whl_resp, f_out)

        if on_status:
            on_status(f"Instalando motor do YouTube v{latest_ver}...")

        # Extrai os pacotes
        with zipfile.ZipFile(temp_whl, "r") as zf:
            for member in zf.namelist():
                # Extrai apenas os diretórios yt_dlp e dist-info
                if member.startswith("yt_dlp/") or member.startswith("yt_dlp-"):
                    zf.extract(member, PACKAGES_DIR)

        if os.path.exists(temp_whl):
            try:
                os.remove(temp_whl)
            except Exception:
                pass

        # Garante PACKAGES_DIR no início do sys.path
        if PACKAGES_DIR not in sys.path:
            sys.path.insert(0, PACKAGES_DIR)

        # Recarrega módulos em memória se já foram importados
        import importlib
        if "yt_dlp" in sys.modules:
            importlib.reload(sys.modules["yt_dlp"])
        if "yt_dlp.version" in sys.modules:
            importlib.reload(sys.modules["yt_dlp.version"])

        new_installed_ver = get_installed_ytdlp_version()
        log_info(f"yt-dlp atualizado com sucesso para v{new_installed_ver}!")
        return True, f"Motor do YouTube atualizado com sucesso para v{new_installed_ver}!"

    except Exception as e:
        log_warning(f"Falha ao checar/atualizar yt-dlp: {e}")
        return False, f"Falha na checagem do yt-dlp: {e}"

# ------------------------------------------------------------------------------
# 2. ATUALIZAÇÃO DO APLICATIVO (NEXUS FETCH)
# ------------------------------------------------------------------------------

def check_app_update() -> Optional[Dict]:
    """
    Checa via GitHub API se houve commit novo na pasta dist para o binário atual.
    Retorna dicionário com dados da atualização ou None se já estiver atualizado.
    """
    try:
        bin_name = get_current_binary_name()
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits?path=dist/{bin_name}&page=1&per_page=1"
        
        req = urllib.request.Request(api_url, headers={"User-Agent": "NexusFetch-AutoUpdater"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            commits = json.loads(resp.read().decode("utf-8"))

        if not commits:
            return None

        latest_commit = commits[0]
        commit_sha = latest_commit.get("sha", "")
        commit_date_str = latest_commit.get("commit", {}).get("committer", {}).get("date", "")
        commit_msg = latest_commit.get("commit", {}).get("message", "").splitlines()[0]

        # Converte ISO date para timestamp UTC
        import datetime
        dt = datetime.datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
        commit_timestamp = dt.timestamp()

        # Determina o timestamp da compilação do executável atual
        exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        local_mtime = os.path.getmtime(exe_path) if os.path.exists(exe_path) else 0

        # Lê último commit registrado se existir
        version_file = os.path.join(USER_DATA_DIR, "installed_commit.json")
        installed_sha = ""
        if os.path.exists(version_file):
            try:
                with open(version_file, "r") as vf:
                    installed_sha = json.load(vf).get("sha", "")
            except Exception:
                pass

        # Considera novo se o commit_timestamp for mais de 60s superior à data do arquivo ou se SHA gravado for diferente
        is_newer = (commit_timestamp > (local_mtime + 60)) and (installed_sha != commit_sha)

        if is_newer:
            raw_download_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/dist/{bin_name}"
            return {
                "sha": commit_sha,
                "date": commit_date_str,
                "timestamp": commit_timestamp,
                "message": commit_msg,
                "download_url": raw_download_url,
                "binary_name": bin_name,
            }

        return None

    except Exception as e:
        log_warning(f"Erro ao checar atualizacao do aplicativo: {e}")
        return None

def download_app_update(update_info: Dict, on_progress: Optional[Callable[[float], None]] = None) -> bool:
    """Baixa o executável atualizado em segundo plano e prepara para instalação."""
    try:
        os.makedirs(UPDATE_DIR, exist_ok=True)
        bin_name = update_info.get("binary_name", get_current_binary_name())
        temp_dest = os.path.join(UPDATE_DIR, f"{bin_name}.downloading")
        ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")

        url = update_info.get("download_url")
        req = urllib.request.Request(url, headers={"User-Agent": "NexusFetch-AutoUpdater"})

        with urllib.request.urlopen(req, timeout=120) as resp:
            total_bytes = int(resp.getheader("Content-Length", 0))
            downloaded = 0

            with open(temp_dest, "wb") as f_out:
                chunk_size = 1024 * 512
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    downloaded += len(chunk)

                    if on_progress and total_bytes > 0:
                        pct = (downloaded / total_bytes) * 100.0
                        on_progress(pct)

        # Valida tamanho do binário baixado (> 20 MB)
        if os.path.exists(temp_dest) and os.path.getsize(temp_dest) > 20 * 1024 * 1024:
            if os.path.exists(ready_dest):
                os.remove(ready_dest)
            os.rename(temp_dest, ready_dest)

            # Salva metadados do update pronto
            info_file = os.path.join(UPDATE_DIR, "update_info.json")
            with open(info_file, "w") as vf:
                json.dump(update_info, vf)

            log_info(f"Atualizacao do executavel baixada e pronta em: {ready_dest}")
            return True

        if os.path.exists(temp_dest):
            os.remove(temp_dest)
        return False

    except Exception as e:
        log_error(f"Erro ao baixar atualizacao do executavel: {e}")
        return False

def is_update_ready() -> bool:
    """Verifica se já existe uma atualização completamente baixada e pronta para ser aplicada."""
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")
    return os.path.exists(ready_dest) and os.path.getsize(ready_dest) > 20 * 1024 * 1024

def apply_app_update_and_restart():
    """Substitui o binário em execução pelo baixado e reinicia a aplicação imediatamente."""
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")

    if not os.path.exists(ready_dest):
        log_error("Tentativa de atualizar sem arquivo pronto.")
        return False

    # Registra o SHA instalado
    info_file = os.path.join(UPDATE_DIR, "update_info.json")
    if os.path.exists(info_file):
        try:
            shutil.copyfile(info_file, os.path.join(USER_DATA_DIR, "installed_commit.json"))
        except Exception:
            pass

    target_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])

    if sys.platform == "win32":
        # Script batch autolimpante desanexado para substituir o executável e reiniciar
        batch_script = os.path.join(tempfile.gettempdir(), f"nexus_updater_{int(time.time())}.bat")
        script_content = f"""@echo off
timeout /t 1 /nobreak > NUL
:retry
move /y "{ready_dest}" "{target_exe}" > NUL 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak > NUL
    goto retry
)
start "" "{target_exe}" --updated
del "%~f0"
"""
        with open(batch_script, "w") as f:
            f.write(script_content)

        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(["cmd.exe", "/c", batch_script], creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS)
        os._exit(0)

    else:
        # Linux
        try:
            os.chmod(ready_dest, 0o755)
            shutil.move(ready_dest, target_exe)
            subprocess.Popen([target_exe, "--updated"])
            os._exit(0)
        except Exception as e:
            log_error(f"Erro ao reiniciar no Linux: {e}")
            return False

def apply_pending_update_if_any() -> bool:
    """
    Chamado no início de main.py.
    Se o programa tiver sido fechado anteriormente com um download de update pendente,
    substitui o executável antes de inicializar a UI e reabre atualizado.
    """
    if "--updated" in sys.argv:
        # Já iniciou após atualização, limpa resquícios se houver
        bin_name = get_current_binary_name()
        ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")
        if os.path.exists(ready_dest):
            try:
                os.remove(ready_dest)
            except Exception:
                pass
        return False

    if is_update_ready():
        # Se estamos no executável empacotado, aplica e reinicia
        if getattr(sys, "frozen", False):
            log_info("Atualizacao pendente detectada na inicializacao. Aplicando...")
            apply_app_update_and_restart()
            return True

    return False
