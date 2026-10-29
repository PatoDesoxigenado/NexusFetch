#!/usr/bin/env bash
# ==============================================================================
# Script de Compilação do Nexus Fetch para Sistemas Linux (Binário ELF Standalone)
# ==============================================================================

# 1. Proteção contra execução no Git Bash do Windows
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        echo "============================================================"
        echo "  ⚠️  AVISO: Você está executando no Git Bash do Windows!"
        echo "============================================================"
        echo "O Git Bash roda sobre o Windows e não pode gerar binários ELF de Linux."
        echo ""
        echo "Para compilar para Linux pelo Windows, use o arquivo:"
        echo "  👉 build_linux_via_wsl.bat (dois cliques)"
        echo "Ou execute no PowerShell / CMD:"
        echo "  👉 wsl -d Ubuntu -- bash -c 'cd /mnt/c/Users/Luiz/Documents/GitHub/NexusFetch && ./build_linux.sh'"
        echo "============================================================"
        exit 1
        ;;
esac

set -e

echo "============================================================"
echo "  🚀 INICIANDO COMPILAÇÃO DO NEXUS FETCH PARA LINUX (ELF)"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 2. Garante python3 e dependências
if ! command -v python3 &> /dev/null; then
    echo "❌ Erro: python3 não encontrado. Instale com: sudo apt update && sudo apt install -y python3 python3-pip python3-tk python3-venv"
    exit 1
fi

echo "[1/4] Configurando ambiente e dependências..."
VENV_DIR="/tmp/nexus_venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR" 2>/dev/null || true
fi

if [ -f "$VENV_DIR/bin/pip" ]; then
    PYTHON_EXEC="$VENV_DIR/bin/python"
    PIP_EXEC="$VENV_DIR/bin/pip"
else
    PYTHON_EXEC="python3"
    PIP_EXEC="pip3"
fi

"$PIP_EXEC" install -r requirements.txt --quiet || "$PIP_EXEC" install -r requirements.txt --break-system-packages --ignore-installed --quiet

CTK_DIR=$("$PYTHON_EXEC" -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))")
ASSETS_DIR="$SCRIPT_DIR/assets"
ICON_PNG="$ASSETS_DIR/icon.png"

echo "[2/4] Diretório de Assets: $ASSETS_DIR"
echo "[2/4] Diretório do CustomTkinter: $CTK_DIR"

echo "[3/4] Executando PyInstaller para Linux..."
"$PYTHON_EXEC" -m PyInstaller main.py \
    --name="NexusFetch" \
    --noconsole \
    --onefile \
    --icon="$ICON_PNG" \
    --add-data="$ASSETS_DIR:assets" \
    --add-data="$CTK_DIR:customtkinter" \
    --collect-all="yt_dlp" \
    --collect-all="customtkinter" \
    --collect-all="curl_cffi" \
    --hidden-import="_cffi_backend" \
    --hidden-import="PIL" \
    --hidden-import="PIL.Image" \
    --hidden-import="PIL.ImageTk" \
    --clean \
    -y

if [ -f "$SCRIPT_DIR/dist/NexusFetch" ]; then
    chmod +x "$SCRIPT_DIR/dist/NexusFetch"
    SIZE_MB=$(du -m "$SCRIPT_DIR/dist/NexusFetch" | cut -f1)
    echo "============================================================"
    echo "  ✨ COMPILAÇÃO PARA LINUX CONCLUÍDA COM SUCESSO!"
    echo "  📁 Binário executável gerado: dist/NexusFetch"
    echo "  ⚖️  Tamanho final: ~${SIZE_MB} MB"
    echo "============================================================"
    echo "Para rodar no Linux: ./dist/NexusFetch"
else
    echo "❌ Erro: O binário dist/NexusFetch não foi gerado."
    exit 1
fi
