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
    """Verifica se já existe uma atualização completamente baixada e pronta para ser aplicada."""
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")
    return os.path.exists(ready_dest) and os.path.getsize(ready_dest) > 20 * 1024 * 1024


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


def _ps_escape(value: str) -> str:
    """Escapa aspas simples para uso seguro em literais PowerShell '...'."""
    return value.replace("'", "''")


def _build_windows_updater_script(
    ready_dest: str,
    target_exe: str,
    child_pid: int,
    parent_pid: int,
    log_file: str,
) -> str:
    """Gera o script PowerShell desanexado responsável por aguardar o encerramento completo e reiniciar."""
    ps_ready = _ps_escape(ready_dest)
    ps_target = _ps_escape(target_exe)
    ps_log = _ps_escape(log_file)
    return f"""$ErrorActionPreference = 'Stop'
$ReadyDest = '{ps_ready}'
$TargetExe = '{ps_target}'
$BackupExe = "$TargetExe.bak"
$LogFile = '{ps_log}'
$ChildPid = {child_pid}
$ParentPid = {parent_pid}

function Write-UpdaterLog([string]$Msg) {{
    try {{
        $dir = Split-Path -Parent $LogFile
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {{
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }}
        $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -LiteralPath $LogFile -Value "[$ts] $Msg" -Encoding UTF8
    }} catch {{}}
}}

function Wait-PidExit([int]$TargetPid, [int]$MaxWaitMs) {{
    $elapsed = 0
    while ($elapsed -lt $MaxWaitMs) {{
        $proc = Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
        if (-not $proc) {{ return $true }}
        Start-Sleep -Milliseconds 250
        $elapsed += 250
    }}
    return $false
}}

Write-UpdaterLog "Iniciando atualizacao: ChildPid=$ChildPid ParentPid=$ParentPid Target=$TargetExe"

# 1. Aguarda o processo Python filho encerrar
[void](Wait-PidExit -TargetPid $ChildPid -MaxWaitMs 15000)

# 2. Se o processo pai for o bootloader do PyInstaller (NexusFetch.exe), aguarda ele limpar _MEI* e liberar o lock
$parentProc = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
if ($parentProc -and $parentProc.ProcessName -like 'NexusFetch*') {{
    Write-UpdaterLog "Aguardando bootloader PyInstaller (PID=$ParentPid) encerrar..."
    [void](Wait-PidExit -TargetPid $ParentPid -MaxWaitMs 15000)
}}

Start-Sleep -Milliseconds 400

if (-not (Test-Path -LiteralPath $ReadyDest)) {{
    Write-UpdaterLog "ERRO: Arquivo pronto nao encontrado: $ReadyDest"
    exit 1
}}

# 3. Backup e substituicao com retry para tolerar locks transitorios de antivirus/SO
$moved = $false
for ($i = 1; $i -le 25; $i++) {{
    try {{
        if (Test-Path -LiteralPath $TargetExe) {{
            Move-Item -LiteralPath $TargetExe -Destination $BackupExe -Force
        }}
        Move-Item -LiteralPath $ReadyDest -Destination $TargetExe -Force
        $moved = $true
        Write-UpdaterLog "Binario substituido com sucesso na tentativa $i."
        break
    }} catch {{
        Write-UpdaterLog "Tentativa $i falhou: $($_.Exception.Message)"
        if ((-not (Test-Path -LiteralPath $TargetExe)) -and (Test-Path -LiteralPath $BackupExe)) {{
            try {{ Move-Item -LiteralPath $BackupExe -Destination $TargetExe -Force }} catch {{}}
        }}
        Start-Sleep -Milliseconds 400
    }}
}}

if (-not $moved) {{
    Write-UpdaterLog "ERRO CRITICO: Nao foi possivel substituir $TargetExe apos 25 tentativas."
    exit 1
}}

if (Test-Path -LiteralPath $BackupExe) {{
    Remove-Item -LiteralPath $BackupExe -Force -ErrorAction SilentlyContinue
}}

# 4. Limpa quaisquer variaveis PyInstaller residuais no ambiente antes de relancar
Get-ChildItem Env: | Where-Object {{ $_.Name -like '_MEI*' -or $_.Name -like '_PYI_*' }} | Remove-Item -ErrorAction SilentlyContinue
Remove-Item Env:TCL_LIBRARY, Env:TK_LIBRARY, Env:PYTHONHOME, Env:PYTHONPATH -ErrorAction SilentlyContinue

Start-Sleep -Milliseconds 300

try {{
    $workDir = Split-Path -Parent $TargetExe
    Start-Process -FilePath $TargetExe -ArgumentList '--updated' -WorkingDirectory $workDir | Out-Null
    Write-UpdaterLog "Novo processo iniciado com sucesso (--updated)."
}} catch {{
    Write-UpdaterLog "ERRO ao iniciar novo processo: $($_.Exception.Message)"
}}

Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""


def _apply_windows_update_and_restart(ready_dest: str, target_exe: str) -> bool:
    """Executa atualização desanexada via PowerShell no Windows e encerra o processo atual."""
    ps_script = os.path.join(tempfile.gettempdir(), f"nexus_updater_{os.getpid()}_{int(time.time())}.ps1")
    updater_log = os.path.join(LOG_DIR, "updater.log")
    script_content = _build_windows_updater_script(
        ready_dest=ready_dest,
        target_exe=target_exe,
        child_pid=os.getpid(),
        parent_pid=os.getppid(),
        log_file=updater_log,
    )
    with open(ps_script, "w", encoding="utf-8-sig") as f:
        f.write(script_content)

    CREATE_NO_WINDOW = 0x08000000
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    env = _build_clean_subprocess_env()
    ps_exe = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
    )
    if not os.path.exists(ps_exe):
        ps_exe = "powershell.exe"

    log_info(f"Disparando atualizador PowerShell desanexado: {ps_script}")
    subprocess.Popen(
        [
            ps_exe,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden",
            "-File", ps_script,
        ],
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        env=env,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logging.shutdown()
    os._exit(0)
    return True


def _apply_linux_update_and_restart(ready_dest: str, target_exe: str) -> bool:
    """Substitui o binário ELF atomicamente no Linux e relança o processo limpo."""
    backup_exe = f"{target_exe}.bak"
    try:
        os.chmod(ready_dest, 0o755)
        if os.path.exists(target_exe):
            shutil.copy2(target_exe, backup_exe)
        shutil.move(ready_dest, target_exe)
        if os.path.exists(backup_exe):
            try:
                os.remove(backup_exe)
            except OSError:
                pass

        env = _build_clean_subprocess_env()
        log_info(f"Relancando binario Linux atualizado: {target_exe}")
        subprocess.Popen(
            [target_exe, "--updated"],
            env=env,
            start_new_session=True,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logging.shutdown()
        os._exit(0)
        return True
    except Exception as e:
        log_error(f"Erro ao reiniciar no Linux: {e}")
        if (not os.path.exists(target_exe)) and os.path.exists(backup_exe):
            try:
                shutil.move(backup_exe, target_exe)
            except OSError:
                pass
        return False


def apply_app_update_and_restart() -> bool:
    """Substitui o binário em execução pelo baixado e reinicia a aplicação imediatamente."""
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")

    if not os.path.exists(ready_dest):
        log_error("Tentativa de atualizar sem arquivo pronto.")
        return False

    if not _is_valid_binary_header(ready_dest, bin_name):
        log_error(f"Arquivo de atualização corrompido ou incompatível: {ready_dest}")
        try:
            os.remove(ready_dest)
        except OSError:
            pass
        return False

    # Registra o SHA instalado
    info_file = os.path.join(UPDATE_DIR, "update_info.json")
    if os.path.exists(info_file):
        try:
            shutil.copyfile(info_file, os.path.join(USER_DATA_DIR, "installed_commit.json"))
        except Exception as e:
            log_warning(f"Não foi possível registrar installed_commit.json: {e}")

    target_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    log_info(f"Aplicando atualização: ready={ready_dest} -> target={target_exe}")

    if sys.platform == "win32":
        return _apply_windows_update_and_restart(ready_dest, target_exe)
    return _apply_linux_update_and_restart(ready_dest, target_exe)


def _cleanup_update_artifacts() -> None:
    """Remove arquivos temporários residuais após uma atualização bem-sucedida."""
    bin_name = get_current_binary_name()
    ready_dest = os.path.join(UPDATE_DIR, f"{bin_name}.ready")
    target_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    candidates = [ready_dest, f"{target_exe}.bak"]
    temp_dir = tempfile.gettempdir()
    candidates.extend(glob.glob(os.path.join(temp_dir, "nexus_updater_*.ps1")))
    candidates.extend(glob.glob(os.path.join(temp_dir, "nexus_updater_*.bat")))
    for path in candidates:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def apply_pending_update_if_any() -> bool:
    """
    Chamado no início de main.py.
    Se o programa tiver sido fechado anteriormente com um download de update pendente,
    substitui o executável antes de inicializar a UI e reabre atualizado.
    """
    if "--updated" in sys.argv:
        log_info("Aplicativo reiniciado com sucesso após atualização (--updated).")
        _cleanup_update_artifacts()
        return False

    if is_update_ready():
        if getattr(sys, "frozen", False):
            log_info("Atualização pendente detectada na inicialização. Aplicando...")
            apply_app_update_and_restart()
            return True

    return False
