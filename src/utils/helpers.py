"""Funções auxiliares para formatação e manipulação de arquivos."""
import re
import os
from typing import Union

def format_bytes(bytes_count: Union[int, float, None]) -> str:
    """Converte contagem de bytes para string legível (ex: 15.4 MB)."""
    if bytes_count is None or bytes_count <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    val = float(bytes_count)
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1
    return f"{val:.1f} {units[unit_idx]}"

def format_duration(seconds: Union[int, float, None]) -> str:
    """Converte segundos para formato MM:SS ou HH:MM:SS."""
    if seconds is None or seconds < 0:
        return "00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def sanitize_filename(filename: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos no Windows."""
    # Substitui caracteres ilegais: <>:"/\|?*
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
    cleaned = cleaned.strip().strip('.')
    return cleaned or "download"

def ensure_directory(path: str) -> str:
    """Garante que o diretório exista e retorna o caminho absoluto."""
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)
