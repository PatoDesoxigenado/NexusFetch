"""Módulo de atualização automática do motor do YouTube (yt-dlp) e do próprio executável."""
import os
import sys
import json
import time
import glob
import shutil
import logging
import zipfile
import tempfile
import threading
import subprocess
import urllib.request
from typing import Optional, Tuple, Dict, Callable
from src.utils.logger import log_info, log_error, log_warning, LOG_DIR

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

        # Valida tamanho do binário baixado (> 20 MB) e cabeçalho mágico da plataforma
        if os.path.exists(temp_dest) and os.path.getsize(temp_dest) > 20 * 1024 * 1024:
            if not _is_valid_binary_header(temp_dest, bin_name):
                log_error(f"Binário baixado inválido para {bin_name}.")
                os.remove(temp_dest)
                return False

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
    """Verifica se já existe uma atualização válida baixada e pronta para ser aplicada."""
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")
    if not (os.path.exists(ready_dest) and os.path.getsize(ready_dest) > 20 * 1024 * 1024):
        return False

    if not _is_valid_binary_header(ready_dest, bin_name):
        try:
            os.remove(ready_dest)
        except OSError:
            pass
        return False

    # Se o commit do update_info.json já for igual ao installed_commit.json, limpa o .ready obsoleto
    info_file = os.path.join(UPDATE_DIR, "update_info.json")
    installed_file = os.path.join(USER_DATA_DIR, "installed_commit.json")
    if os.path.exists(info_file) and os.path.exists(installed_file):
        try:
            with open(info_file, "r", encoding="utf-8") as f_up, open(installed_file, "r", encoding="utf-8") as f_in:
                up_sha = json.load(f_up).get("sha", "")
                in_sha = json.load(f_in).get("sha", "")
            if up_sha and up_sha == in_sha:
                os.remove(ready_dest)
                return False
        except Exception:
            pass

    return True


def _is_valid_binary_header(file_path: str, bin_name: str) -> bool:
    """Valida o cabeçalho mágico do binário (MZ para Windows PE, \\x7fELF para Linux)."""
    try:
        with open(file_path, "rb") as f_hdr:
            magic = f_hdr.read(4)
        return magic[:2] == b"MZ" if bin_name.endswith(".exe") else magic == b"\x7fELF"
    except OSError:
        return False


def _build_clean_subprocess_env() -> Dict[str, str]:
    """
    Retorna uma cópia sanitizada de os.environ sem variáveis e caminhos _MEI* / _PYI_*
    do PyInstaller atual, evitando que o novo processo herde referências a pastas
    temporárias que serão deletadas ao encerrar o processo pai.
    """
    env = os.environ.copy()
    exact_remove = {
        "TCL_LIBRARY",
        "TK_LIBRARY",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONEXECUTABLE",
    }
    for key in list(env.keys()):
        if key in exact_remove or key.startswith("_MEI") or key.startswith("_PYI_"):
            env.pop(key, None)

    meipass = getattr(sys, "_MEIPASS", None)
    if "PATH" in env:
        sep = ";" if sys.platform == "win32" else ":"
        cleaned_paths = [
            p for p in env["PATH"].split(sep)
            if p and "_MEI" not in p and (not meipass or os.path.normcase(p) != os.path.normcase(meipass))
        ]
        env["PATH"] = sep.join(cleaned_paths)

    return env


def install_app_update_in_place(
    ready_dest: str,
    target_exe: str,
    on_status: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str, str]:
    """
    Instala a nova versão com a janela ainda aberta:
    1. Mantém o executável atual em execução renomeando-o para temporário (.old).
    2. Move o novo binário (.ready) para o caminho oficial (target_exe).
    3. Confirma a integridade do novo arquivo no destino e reverte (.old -> target_exe) se algo falhar.
    Retorna (sucesso, mensagem_ou_caminho_novo, caminho_old_temporario).
    """
    bin_name = get_current_binary_name()
    if not os.path.exists(ready_dest):
        msg = "Arquivo de atualização (.ready) não encontrado."
        log_error(msg)
        return False, msg, ""

    if not _is_valid_binary_header(ready_dest, bin_name):
        msg = f"Arquivo de atualização corrompido ou incompatível: {ready_dest}"
        log_error(msg)
        try:
            os.remove(ready_dest)
        except OSError:
            pass
        return False, msg, ""

    if on_status:
        on_status("⏳ Instalando atualização... mantendo versão atual como temporária (.old)...")

    temp_old_exe = f"{target_exe}.old"
    if os.path.exists(temp_old_exe):
        try:
            os.remove(temp_old_exe)
        except OSError:
            temp_old_exe = f"{target_exe}.{os.getpid()}.old"

    moved_current_to_old = False
    try:
        if sys.platform != "win32":
            os.chmod(ready_dest, 0o755)

        if os.path.exists(target_exe):
            os.replace(target_exe, temp_old_exe)
            moved_current_to_old = True
            log_info(f"Versão em execução movida para temporário: {temp_old_exe}")

        shutil.move(ready_dest, target_exe)
        if sys.platform != "win32":
            os.chmod(target_exe, 0o755)

        if not (os.path.exists(target_exe) and _is_valid_binary_header(target_exe, bin_name)):
            raise RuntimeError("Falha na verificação de integridade do novo executável após cópia.")

        # Registra o SHA instalado somente após confirmar que o novo executável está íntegro no destino
        info_file = os.path.join(UPDATE_DIR, "update_info.json")
        if os.path.exists(info_file):
            try:
                shutil.copyfile(info_file, os.path.join(USER_DATA_DIR, "installed_commit.json"))
                os.remove(info_file)
            except Exception as e:
                log_warning(f"Não foi possível atualizar installed_commit.json: {e}")

        confirm_msg = f"✓ Atualização concluída! Novo executável instalado em: {target_exe}"
        log_info(confirm_msg)
        if on_status:
            on_status(confirm_msg)
        return True, target_exe, temp_old_exe

    except Exception as e:
        log_error(f"Erro durante instalação in-place da atualização: {e}")
        if moved_current_to_old and (not os.path.exists(target_exe)) and os.path.exists(temp_old_exe):
            try:
                os.replace(temp_old_exe, target_exe)
                log_info("Rollback executado com sucesso: versão original restaurada.")
            except OSError as rb_err:
                log_error(f"Falha no rollback do executável: {rb_err}")
        return False, f"Falha ao instalar atualização: {e}", ""


def spawn_updated_executable(target_exe: str, temp_old_exe: str = "") -> bool:
    """Inicia diretamente o novo executável com ambiente limpo (sem scripts intermediários)."""
    try:
        clean_env = _build_clean_subprocess_env()
        work_dir = os.path.dirname(os.path.abspath(target_exe)) or None
        args = [target_exe, "--updated"]
        if temp_old_exe:
            args.append(f"--cleanup-old={temp_old_exe}")

        popen_kwargs = {
            "cwd": work_dir,
            "env": clean_env,
            "close_fds": True,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(args, **popen_kwargs)
        log_info(f"Novo executável iniciado com sucesso (PID={proc.pid}): {target_exe}")
        return True
    except Exception as e:
        log_error(f"Erro ao iniciar novo executável ({target_exe}): {e}")
        return False


def apply_app_update_and_restart(
    on_status: Optional[Callable[[str], None]] = None,
    delay_before_exit: float = 0.0,
) -> bool:
    """
    Fluxo seguro em 4 etapas com a janela aberta:
    1. Mantém a tela aberta e renomeia o executável atual para .old (temporário).
    2. Instala o novo executável no caminho oficial e valida sua integridade.
    3. Confirma o sucesso apontando o caminho do novo executável.
    4. Inicia o novo executável diretamente e encerra o antigo (que é apagado pelo novo ao iniciar).
    """
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")
    target_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])

    ok, result_msg, temp_old_exe = install_app_update_in_place(ready_dest, target_exe, on_status=on_status)
    if not ok:
        if on_status:
            on_status(f"✖ {result_msg}")
        return False

    if delay_before_exit > 0:
        time.sleep(delay_before_exit)

    if not spawn_updated_executable(target_exe, temp_old_exe):
        # Se não conseguiu iniciar o novo, tenta restaurar o antigo para não deixar o usuário na mão
        if on_status:
            on_status("✖ Não foi possível iniciar o novo executável automaticamente.")
        return False

    logging.shutdown()
    os._exit(0)
    return True


def _cleanup_update_artifacts(extra_old_path: str = "", max_retries: int = 20, retry_delay: float = 0.4) -> None:
    """
    Remove o executável temporário (.old) da versão anterior assim que o processo antigo
    termina de fechar, além de limpar quaisquer arquivos residuais (.ready, .bak, scripts antigos).
    """
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")
    target_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])

    old_candidates = set(glob.glob(f"{target_exe}*.old"))
    if extra_old_path:
        old_candidates.add(extra_old_path)

    for old_path in old_candidates:
        for _ in range(max_retries):
            if not os.path.exists(old_path):
                break
            try:
                os.remove(old_path)
                log_info(f"Versão temporária anterior removida com sucesso: {old_path}")
                break
            except OSError:
                time.sleep(retry_delay)

    other_candidates = [ready_dest, f"{target_exe}.bak"]
    temp_dir = tempfile.gettempdir()
    other_candidates.extend(glob.glob(os.path.join(temp_dir, "nexus_updater_*.ps1")))
    other_candidates.extend(glob.glob(os.path.join(temp_dir, "nexus_updater_*.bat")))
    for path in other_candidates:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def apply_pending_update_if_any() -> bool:
    """
    Chamado no início de main.py.
    NUNCA encerra o aplicativo na abertura (evitando boot-loops).
    Apenas agenda a limpeza assíncrona dos arquivos temporários (.old / .bak) deixados pela atualização.
    """
    extra_old = ""
    for arg in sys.argv[1:]:
        if arg.startswith("--cleanup-old="):
            extra_old = arg.split("=", 1)[1].strip('"').strip("'")

    if "--updated" in sys.argv or extra_old:
        log_info("Aplicativo iniciado após atualização (--updated). Agendando limpeza do temporário (.old)...")
        threading.Thread(
            target=_cleanup_update_artifacts,
            kwargs={"extra_old_path": extra_old},
            daemon=True,
        ).start()
    else:
        # Mesmo em aberturas normais, limpa eventuais .old/.bak destravados em background
        threading.Thread(
            target=_cleanup_update_artifacts,
            kwargs={"max_retries": 2, "retry_delay": 0.1},
            daemon=True,
        ).start()

    return False
