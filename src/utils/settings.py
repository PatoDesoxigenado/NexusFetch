"""Persistência leve e atômica de preferências do usuário em ~/.nexusfetch/settings.json."""
import os
import json
import threading
from typing import Any, Dict

from src.config import DEFAULT_DOWNLOAD_DIR
from src.utils.logger import log_warning

USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".nexusfetch")
SETTINGS_FILE = os.path.join(USER_DATA_DIR, "settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "converter_output_dir": DEFAULT_DOWNLOAD_DIR,
    "preferred_format": "video",
    "preferred_quality": "Máxima Resolução",
    "notifications_enabled": True,
}

_settings_lock = threading.Lock()


def load_settings() -> Dict[str, Any]:
    """Carrega preferências do disco mesclando com os padrões seguros."""
    merged = dict(DEFAULT_SETTINGS)
    with _settings_lock:
        if not os.path.exists(SETTINGS_FILE):
            return merged
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                merged.update(raw)
        except Exception as e:
            log_warning(f"Falha ao ler settings.json (usando padrões): {e}")

    # Sanitiza valores críticos
    if str(merged.get("theme", "")).lower() not in ("light", "dark"):
        merged["theme"] = DEFAULT_SETTINGS["theme"]
    else:
        merged["theme"] = str(merged["theme"]).lower()

    if not merged.get("download_dir") or not isinstance(merged["download_dir"], str):
        merged["download_dir"] = DEFAULT_DOWNLOAD_DIR
    if not merged.get("converter_output_dir") or not isinstance(merged["converter_output_dir"], str):
        merged["converter_output_dir"] = DEFAULT_DOWNLOAD_DIR

    return merged


def save_settings(settings: Dict[str, Any]) -> bool:
    """Persiste preferências de forma atômica (.tmp -> os.replace) para evitar corrupção."""
    with _settings_lock:
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            tmp_path = f"{SETTINGS_FILE}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, SETTINGS_FILE)
            return True
        except Exception as e:
            log_warning(f"Falha ao salvar settings.json: {e}")
            return False


def get_setting(key: str, default: Any = None) -> Any:
    """Lê uma chave específica das preferências."""
    data = load_settings()
    return data.get(key, DEFAULT_SETTINGS.get(key, default))


def update_setting(key: str, value: Any) -> bool:
    """Atualiza e persiste uma única preferência mantendo as demais intactas."""
    data = load_settings()
    data[key] = value
    return save_settings(data)
