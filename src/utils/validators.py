"""Validação inteligente de URLs e detecção cruzada entre plataformas."""
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from src.config import MODULE_YOUTUBE, MODULE_INSTAGRAM, MODULE_TWITTER, MODULES

class ValidationStatus(Enum):
    VALID = "valid"
    CROSS_MATCH = "cross_match"
    INVALID = "invalid"

@dataclass
class ValidationResult:
    status: ValidationStatus
    url: str
    detected_module: Optional[str] = None
    suggested_module: Optional[str] = None
    suggested_label: Optional[str] = None
    message: str = ""

# Padrões Regex
PATTERNS = {
    MODULE_YOUTUBE: [
        r'(?:https?:\/\/)?(?:www\.|m\.|music\.)?youtube\.com\/watch\?v=[a-zA-Z0-9_-]{11}',
        r'(?:https?:\/\/)?youtu\.be\/[a-zA-Z0-9_-]{11}',
        r'(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/shorts\/[a-zA-Z0-9_-]{11}',
        r'(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/live\/[a-zA-Z0-9_-]+',
        r'(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/embed\/[a-zA-Z0-9_-]{11}',
    ],
    MODULE_INSTAGRAM: [
        r'(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|reels|tv)\/[a-zA-Z0-9_-]+',
        r'(?:https?:\/\/)?(?:www\.)?instagr\.am\/(?:p|reel|reels|tv)\/[a-zA-Z0-9_-]+',
        r'(?:https?:\/\/)?(?:www\.)?instagram\.com\/stories\/[a-zA-Z0-9_.-]+\/[0-9]+',
    ],
    MODULE_TWITTER: [
        r'(?:https?:\/\/)?(?:www\.|mobile\.)?(?:twitter\.com|x\.com)\/[a-zA-Z0-9_]+\/status\/[0-9]+',
        r'(?:https?:\/\/)?(?:www\.|mobile\.)?(?:twitter\.com|x\.com)\/i\/status\/[0-9]+',
    ],
}

def clean_url(raw_url: str) -> str:
    """Higieniza e normaliza o link inserido."""
    url = raw_url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def detect_platform(url: str) -> Optional[str]:
    """Identifica a qual plataforma a URL pertence através de regex."""
    url = clean_url(url)
    for module_name, regex_list in PATTERNS.items():
        for pattern in regex_list:
            if re.search(pattern, url, re.IGNORECASE):
                return module_name
    return None

def validate_url(raw_url: str, current_module: str) -> ValidationResult:
    """
    Valida a URL informada contra o módulo ativo.
    Se for válida para outro módulo, retorna status CROSS_MATCH com a sugestão de redirecionamento.
    """
    if not raw_url or not raw_url.strip():
        return ValidationResult(
            status=ValidationStatus.INVALID,
            url="",
            message="Por favor, insira uma URL válida."
        )

    url = clean_url(raw_url)
    detected = detect_platform(url)

    if detected == current_module:
        label = MODULES.get(current_module, {}).get("label", current_module.title())
        return ValidationResult(
            status=ValidationStatus.VALID,
            url=url,
            detected_module=detected,
            message=f"Link válido do {label}."
        )

    if detected and detected != current_module:
        target_label = MODULES.get(detected, {}).get("label", detected.title())
        current_label = MODULES.get(current_module, {}).get("label", current_module.title())
        return ValidationResult(
            status=ValidationStatus.CROSS_MATCH,
            url=url,
            detected_module=detected,
            suggested_module=detected,
            suggested_label=target_label,
            message=f"Este link não é do {current_label}, mas pertence à aba \"{target_label}\"."
        )

    return ValidationResult(
        status=ValidationStatus.INVALID,
        url=url,
        message="Link não reconhecido ou plataforma não suportada."
    )
