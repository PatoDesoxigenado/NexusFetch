"""Definições de Tema Adaptativo (Claro/Escuro), Alto Contraste e Tipografia Moderna do Nexus Fetch."""
import sys

def _resolve_fonts():
    """Define a família de fontes moderna por sistema sem instanciar janelas temporárias."""
    if sys.platform == "win32":
        return "Segoe UI Variable Text", "Segoe UI Variable Display"
    elif sys.platform == "darwin":
        return "SF Pro Text", "SF Pro Display"
    else:
        return "DejaVu Sans", "DejaVu Sans"

_FAMILY, _DISPLAY = _resolve_fonts()

class Theme:
    # -------------------------------------------------------------------------
    # 1. Cores de Fundo e Containers Elevados
    # Padrão CustomTkinter: (Modo Claro, Modo Escuro)
    # -------------------------------------------------------------------------
    BG_DARK = ("#F1F3F7", "#0F1015")           # Fundo da janela principal (Claro: Cinza claro moderno / Escuro: Deep Dark)
    BG_CARD = ("#FFFFFF", "#1A1D24")           # Fundo de cards, previews e painéis (Claro: Branco puro / Escuro: Card elevado)
    BG_CARD_LIGHT = ("#F8FAFC", "#242832")     # Containers secundários, listas e cabeçalhos
    BG_INPUT = ("#F1F5F9", "#13151B")          # Fundo de campos de texto e caixas de seleção
    
    # -------------------------------------------------------------------------
    # 2. Bordas e Divisores (Contraste Nítido em Telas Diversas)
    # -------------------------------------------------------------------------
    BORDER = ("#CBD5E1", "#373D4A")            # Borda nítida padrão para cartões
    BORDER_SUBTLE = ("#E2E8F0", "#2A2F3A")     # Divisores internos mais suaves
    BORDER_FOCUS = ("#E50914", "#E50914")      # Vermelho no foco ativo
    
    # -------------------------------------------------------------------------
    # 3. Cores Primárias (Vermelho Nexus)
    # -------------------------------------------------------------------------
    PRIMARY = ("#E50914", "#E50914")           # Vermelho vibrante padrão
    PRIMARY_HOVER = ("#C80812", "#B80710")     # Vermelho mais escuro no hover
    PRIMARY_ACTIVE = ("#FF1F2B", "#FF1F2B")    # Vermelho ativo/clicado
    
    # -------------------------------------------------------------------------
    # 4. Cores Secundárias e Controles Neutros
    # -------------------------------------------------------------------------
    SECONDARY = ("#E2E8F0", "#2A2E39")         # Fundo de botões secundários
    SECONDARY_HOVER = ("#CBD5E1", "#3A404F")   # Hover de botões secundários
    
    # -------------------------------------------------------------------------
    # 5. Módulo Conversor de Mídia (Destaque Violeta de Alto Contraste)
    # -------------------------------------------------------------------------
    CONVERTER_PRIMARY = ("#7C3AED", "#8B5CF6") # Violeta vibrante principal
    CONVERTER_HOVER = ("#6D28D9", "#7C3AED")   # Roxo escuro no hover
    CONVERTER_ACTIVE = ("#5B21B6", "#6D28D9")  # Roxo ativo/clicado
    CONVERTER_BORDER = ("#8B5CF6", "#7C3AED")  # Borda com brilho violeta perceptível
    CONVERTER_BG_LIGHT = ("#F5F3FF", "#1C172E")# Fundo do card explicativo
    CONVERTER_TEXT_BRIGHT = ("#6D28D9", "#C4B5FD") # Roxo no claro, lavanda brilhante no escuro
    
    # -------------------------------------------------------------------------
    # 6. Status, Indicadores e Ações
    # -------------------------------------------------------------------------
    SUCCESS = ("#059669", "#10B981")           # Verde conclusão / pronto
    SUCCESS_HOVER = ("#047857", "#059669")
    WARNING = ("#D97706", "#F59E0B")           # Âmbar aviso
    INFO = ("#2563EB", "#3B82F6")              # Azul informação
    DANGER = ("#DC2626", "#EF4444")            # Vermelho perigo / erro
    
    # -------------------------------------------------------------------------
    # 7. Tipografia e Cores de Texto (Legibilidade e WCAG AA+)
    # -------------------------------------------------------------------------
    TEXT_MAIN = ("#0F172A", "#FFFFFF")         # Quase preto no claro / Branco puro no escuro
    TEXT_NORMAL = ("#1E293B", "#E5E7EB")       # Cinza ardósia / Cinza claro
    TEXT_MUTED = ("#475569", "#B6BCC6")        # Cinza médio nítido
    TEXT_DIM = ("#64748B", "#8B95A5")          # Cinza suave legível
    TEXT_INVERTED = ("#FFFFFF", "#0F1015")     # Cor para sobreposição
    
    # -------------------------------------------------------------------------
    # 8. Escala Tipográfica Moderna
    # -------------------------------------------------------------------------
    FONT_FAMILY = _FAMILY
    FONT_DISPLAY = _DISPLAY
    FONT_TITLE = (_DISPLAY, 20, "bold")
    FONT_SUBTITLE = (_DISPLAY, 14, "bold")
    FONT_BODY = (_FAMILY, 12)
    FONT_BODY_BOLD = (_FAMILY, 12, "bold")
    FONT_BUTTON = (_FAMILY, 12, "bold")
    FONT_SMALL = (_FAMILY, 10)
    FONT_SMALL_BOLD = (_FAMILY, 10, "bold")
    FONT_BADGE = (_FAMILY, 10, "bold")
    FONT_MONO = ("Consolas", 11)
    
    # -------------------------------------------------------------------------
    # 9. Raio de Borda (Corner Radius)
    # -------------------------------------------------------------------------
    CORNER_RADIUS = 10
    CORNER_RADIUS_SM = 6
    CORNER_RADIUS_LG = 14
