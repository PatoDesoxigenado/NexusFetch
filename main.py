"""Ponto de entrada principal do Nexus Fetch."""
import sys
import os

# Adiciona o diretório raiz ao sys.path para garantir importações relativas e absolutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Adiciona pasta de pacotes dinâmicos do usuário ao sys.path para carregar atualizações do yt-dlp
USER_PACKAGES_DIR = os.path.join(os.path.expanduser("~"), ".nexusfetch", "packages")
if os.path.exists(USER_PACKAGES_DIR) and USER_PACKAGES_DIR not in sys.path:
    sys.path.insert(0, USER_PACKAGES_DIR)

def main():
    # Limpa artefatos residuais (.old / .bak) de atualizações anteriores em background (nunca bloqueia a abertura!)
    try:
        from src.utils.updater import apply_pending_update_if_any
        apply_pending_update_if_any()
    except Exception:
        pass

    # No Windows, define o AppUserModelID para exibir o ícone correto na barra de tarefas
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "nexusfetch.downloader.desktop.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    from src.ui.app import NexusFetchApp
    app = NexusFetchApp()
    app.mainloop()

if __name__ == "__main__":
    main()
