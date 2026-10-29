"""Ponto de entrada principal do Nexus Fetch."""
import sys
import os

# Adiciona o diretório raiz ao sys.path para garantir importações relativas e absolutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def main():
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
