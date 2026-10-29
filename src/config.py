"""Configurações globais e constantes do Nexus Fetch."""
import os
import sys
from pathlib import Path

APP_NAME = "Nexus Fetch"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Downloader Desktop de Alta Performance"

# Resolução da Janela
WINDOW_WIDTH = 920
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 840
WINDOW_MIN_HEIGHT = 650

# Módulos Suportados
MODULE_YOUTUBE = "youtube"
MODULE_INSTAGRAM = "instagram"
MODULE_TWITTER = "twitter"

MODULES = {
    MODULE_YOUTUBE: {"label": "YouTube", "icon": "▶"},
    MODULE_INSTAGRAM: {"label": "Instagram", "icon": "📸"},
    MODULE_TWITTER: {"label": "Twitter / X", "icon": "✖"},
}

# Diretório padrão de Downloads
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

# Gerenciamento de Assets (Compatível com PyInstaller --onefile)
def get_resource_path(relative_path: str) -> str:
    """Retorna o caminho absoluto de um recurso, compatível com PyInstaller e modo dev."""
    if hasattr(sys, "_MEIPASS"):
        # Executando empacotado pelo PyInstaller
        base_path = sys._MEIPASS
    else:
        # Executando normalmente em Python
        base_path = Path(__file__).resolve().parent.parent

    return os.path.normpath(os.path.join(base_path, relative_path))

ASSETS_DIR = get_resource_path("assets")
ICON_ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")
ICON_PNG_PATH = os.path.join(ASSETS_DIR, "icon.png")
