"""Script automatizado de compilação do Nexus Fetch para executável Windows (.exe)."""
import os
import sys
import time
import shutil
import subprocess
import PyInstaller.__main__
import customtkinter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def close_existing_process():
    """Fecha instâncias em execução do NexusFetch para permitir a sobrescrita do .exe."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "NexusFetch.exe"], capture_output=True)
        time.sleep(1)
    except Exception:
        pass

def build():
    print("=" * 60)
    print("  [*] INICIANDO COMPILACAO: Nexus Fetch (.exe Standalone)")
    print("=" * 60)

    # Encerra processos antigos se estiverem abertos
    close_existing_process()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, "assets")
    icon_path = os.path.join(assets_dir, "icon.ico")
    ctk_dir = os.path.dirname(customtkinter.__file__)

    sep = ";"

    cmd_args = [
        "main.py",
        "--name=NexusFetch",
        "--noconsole",
        "--onefile",
        f"--icon={icon_path}",
        f"--add-data={assets_dir}{sep}assets",
        f"--add-data={ctk_dir}{sep}customtkinter",
        "--collect-all=yt_dlp",
        "--collect-all=customtkinter",
        "--collect-all=curl_cffi",
        "--hidden-import=_cffi_backend",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageTk",
        "--clean",
        "-y"
    ]

    print(f"\n[1/3] Diretorio de Assets: {assets_dir}")
    print(f"[2/3] Diretorio do CustomTkinter: {ctk_dir}")
    print("[3/3] Executando PyInstaller (pode levar cerca de 1 a 2 minutos)...")

    try:
        PyInstaller.__main__.run(cmd_args)
        
        exe_path = os.path.join(base_dir, "dist", "NexusFetch.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print("\n" + "=" * 60)
            print("  [+] COMPILACAO CONCLUIDA COM SUCESSO!")
            print(f"  [*] Executavel gerado: {exe_path}")
            print(f"  [*] Tamanho final: {size_mb:.2f} MB")
            print("=" * 60)
            return True
        else:
            print("\n[-] Erro: O arquivo .exe nao foi encontrado em dist/.")
            return False

    except Exception as e:
        print(f"\n[-] Erro durante a compilacao: {e}")
        return False

if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
