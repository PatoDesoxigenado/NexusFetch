"""Testes automatizados de UI Desktop e conformidade de Design/Contraste."""
import pytest
from src.ui.theme import Theme

def test_theme_wcag_palette_tokens():
    """Valida que todos os tokens de contraste e tema adaptativo (claro, escuro) estão definidos."""
    # Valida formato de tupla para suporte a Modo Claro e Modo Escuro
    assert isinstance(Theme.BG_DARK, tuple)
    assert Theme.BG_DARK[1] == "#0F1015"
    assert Theme.BG_CARD[0] == "#FFFFFF"
    assert Theme.BG_CARD[1] == "#1A1D24"
    assert Theme.BORDER[1] == "#373D4A"
    assert Theme.TEXT_MAIN[1] == "#FFFFFF"
    assert Theme.TEXT_MAIN[0] == "#0F172A"
    assert Theme.CONVERTER_TEXT_BRIGHT[1] == "#C4B5FD"

def test_typography_scale():
    """Valida a escala de fontes nativas do sistema desktop."""
    assert Theme.FONT_TITLE[1] == 20
    assert Theme.FONT_SUBTITLE[1] == 14
    assert Theme.FONT_BODY[1] == 12
    assert Theme.FONT_BUTTON[1] == 12
    assert Theme.FONT_SMALL[1] == 10

def test_navbar_module_keys():
    """Valida que o componente NavBar possui as 4 abas e índices correspondentes aos atalhos Ctrl+1..4."""
    from src.config import MODULES, MODULE_YOUTUBE, MODULE_CONVERTER
    keys = list(MODULES.keys())
    assert len(keys) == 4
    assert keys[0] == MODULE_YOUTUBE
    assert keys[3] == MODULE_CONVERTER
