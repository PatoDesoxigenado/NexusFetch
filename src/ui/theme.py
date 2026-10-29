"""Definições de Tema e Paleta de Cores do Nexus Fetch."""

class Theme:
    # Cores de Fundo e Containers
    BG_DARK = "#0D0E11"           # Fundo da janela principal
    BG_CARD = "#16171B"           # Fundo de cards, previews e seções
    BG_CARD_LIGHT = "#1F2126"     # Containers secundários
    BG_INPUT = "#131417"          # Fundo de campos de texto
    
    # Bordas e Divisores
    BORDER = "#2B2D33"
    BORDER_FOCUS = "#E50914"
    
    # Cores Primárias (Vermelho Nexus)
    PRIMARY = "#E50914"           # Vermelho vibrante padrão
    PRIMARY_HOVER = "#B80710"     # Vermelho mais escuro no hover
    PRIMARY_ACTIVE = "#FF1F2B"    # Vermelho ativo/clicado
    
    # Cores Secundárias e Acentos
    SECONDARY = "#22242A"
    SECONDARY_HOVER = "#31343C"
    
    # Status e Ações
    SUCCESS = "#10B981"           # Verde conclusão
    SUCCESS_HOVER = "#059669"
    WARNING = "#F59E0B"           # Âmbar aviso
    INFO = "#3B82F6"              # Azul informação
    DANGER = "#EF4444"
    
    # Tipografia e Cores de Texto
    TEXT_MAIN = "#FFFFFF"         # Branco absoluto para títulos e ênfase
    TEXT_MUTED = "#9CA3AF"        # Cinza para descrições e legendas
    TEXT_DIM = "#6B7280"          # Cinza escuro para detalhes sutis
    TEXT_INVERTED = "#000000"     # Preto para sobreposição
    
    # Fontes
    FONT_FAMILY = "Segoe UI"
    FONT_TITLE = ("Segoe UI", 20, "bold")
    FONT_SUBTITLE = ("Segoe UI", 14, "bold")
    FONT_BODY = ("Segoe UI", 12)
    FONT_BODY_BOLD = ("Segoe UI", 12, "bold")
    FONT_SMALL = ("Segoe UI", 10)
    FONT_BADGE = ("Segoe UI", 9, "bold")
    
    # Raio de Borda (Corner Radius)
    CORNER_RADIUS = 10
    CORNER_RADIUS_SM = 6
    CORNER_RADIUS_LG = 14
