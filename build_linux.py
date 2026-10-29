"""Script de compilação do Nexus Fetch para sistemas Linux (Binário ELF Standalone)."""
import os
import sys
import shutil
import subprocess

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def build_on_linux():
    import PyInstaller.__main__
    import customtkinter

    print("=" * 60)
    print("  🚀 COMPILANDO NEXUS FETCH PARA LINUX (ELF STANDALONE)")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, "assets")
    icon_png = os.path.join(assets_dir, "icon.png")
    ctk_dir = os.path.dirname(customtkinter.__file__)

    # No Linux, o separador de add-data é ':'
    sep = ":"

    cmd_args = [
        "main.py",
        "--name=NexusFetch",
        "--noconsole",
        "--onefile",
        f"--icon={icon_png}",
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

    print(f"\n[1/3] Diretório de Assets: {assets_dir}")
    print(f"[2/3] Diretório do CustomTkinter: {ctk_dir}")
    print("[3/3] Executando PyInstaller para Linux...")

    PyInstaller.__main__.run(cmd_args)

    dist_bin = os.path.join(base_dir, "dist", "NexusFetch")
    if os.path.exists(dist_bin):
        os.chmod(dist_bin, 0o755)
        size_mb = os.path.getsize(dist_bin) / (1024 * 1024)
        print("\n" + "=" * 60)
        print("  ✨ COMPILAÇÃO PARA LINUX CONCLUÍDA COM SUCESSO!")
        print(f"  📁 Binário gerado: {dist_bin}")
        print(f"  ⚖️  Tamanho final: {size_mb:.2f} MB")
        print("=" * 60)
        return True
    return False

def build_from_windows():
    print("=" * 60)
    print("  🐧 INFORMAÇÃO DE COMPILAÇÃO: LINUX vs WINDOWS")
    print("=" * 60)
    print("\nVocê está executando este script em um ambiente Windows.")
    print("Binários para Linux (formato ELF) devem ser gerados em ambiente Linux.")
    print("\nComo compilar:")
    print("  1. No Windows com WSL (Ubuntu):")
    print("     wsl -d Ubuntu -- bash -c 'cd \"$(wslpath -u \"$PWD\")\" && ./build_linux.sh'")
    print("\n  2. Em qualquer distribuição Linux real ou Máquina Virtual:")
    print("     chmod +x build_linux.sh")
    print("     ./build_linux.sh")
    print("\n  3. Para compilar o executável de Windows (.exe):")
    print("     python build_exe.py")
    print("=" * 60)

if __name__ == "__main__":
    if sys.platform.startswith("linux"):
        build_on_linux()
    else:
        build_from_windows()
