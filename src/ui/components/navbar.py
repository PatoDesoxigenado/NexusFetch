"""Barra superior de navegação entre plataformas com ícones PNG oficiais, seletor de tema e alerta de atualização."""
import os
import math
import webbrowser
from typing import Callable, Dict, Optional
import customtkinter as ctk
from PIL import Image, ImageDraw

from src.ui.theme import Theme
from src.config import (
    MODULES,
    MODULE_YOUTUBE,
    MODULE_INSTAGRAM,
    MODULE_TWITTER,
    MODULE_CONVERTER,
    LOGO_YOUTUBE_PATH,
    LOGO_INSTAGRAM_PATH,
    LOGO_TWITTER_PATH,
)
from src.utils.logger import log_warning

class NavBar(ctk.CTkFrame):
    def __init__(self, parent, on_module_selected: Callable[[str], None]):
        super().__init__(
            parent,
            fg_color=Theme.BG_CARD,
            height=60,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.pack_propagate(False)
        self.on_module_selected = on_module_selected
        self.current_module = MODULE_YOUTUBE
        self.buttons: Dict[str, ctk.CTkButton] = {}
        self.module_keys = list(MODULES.keys())
        self.platform_icons: Dict[str, ctk.CTkImage] = {}

        self._create_theme_icons()
        self._load_platform_icons()
        self._build_ui()

    def _create_theme_icons(self):
        """Gera ícones vetoriais em alta resolução para Sol e Lua com alinhamento e centralização perfeitos."""
        # Sol dourado perfeitamente simétrico e centrado
        sun = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(sun)
        d.ellipse([20, 20, 44, 44], fill=(245, 158, 11, 255))
        for i in range(8):
            angle = i * (math.pi / 4)
            x1 = 32 + int(15 * math.cos(angle))
            y1 = 32 + int(15 * math.sin(angle))
            x2 = 32 + int(24 * math.cos(angle))
            y2 = 32 + int(24 * math.sin(angle))
            d.line([x1, y1, x2, y2], fill=(245, 158, 11, 255), width=4)

        # Lua azulada elegante
        moon = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        dm = ImageDraw.Draw(moon)
        dm.ellipse([14, 14, 50, 50], fill=(79, 70, 229, 255))
        dm.ellipse([25, 11, 58, 47], fill=(0, 0, 0, 0))

        self.sun_icon = ctk.CTkImage(light_image=sun, dark_image=sun, size=(18, 18))
        self.moon_icon = ctk.CTkImage(light_image=moon, dark_image=moon, size=(18, 18))

    def _load_platform_icons(self):
        """Carrega e otimiza os arquivos PNG das plataformas na pasta assets."""
        try:
            # 1. YouTube Logo Oficial
            if os.path.exists(LOGO_YOUTUBE_PATH):
                yt_img = Image.open(LOGO_YOUTUBE_PATH).convert("RGBA")
                self.platform_icons[MODULE_YOUTUBE] = ctk.CTkImage(
                    light_image=yt_img,
                    dark_image=yt_img,
                    size=(20, 14)
                )

            # 2. Instagram Logo Oficial
            if os.path.exists(LOGO_INSTAGRAM_PATH):
                insta_img = Image.open(LOGO_INSTAGRAM_PATH).convert("RGBA")
                self.platform_icons[MODULE_INSTAGRAM] = ctk.CTkImage(
                    light_image=insta_img,
                    dark_image=insta_img,
                    size=(18, 18)
                )

            # 3. Twitter / X Logo Oficial Normal (preserva a logo original sem filtros)
            if os.path.exists(LOGO_TWITTER_PATH):
                x_img = Image.open(LOGO_TWITTER_PATH).convert("RGBA")
                self.platform_icons[MODULE_TWITTER] = ctk.CTkImage(
                    light_image=x_img,
                    dark_image=x_img,
                    size=(18, 18)
                )

        except Exception as e:
            log_warning(f"Não foi possível carregar logos PNG de assets: {e}")

    def _build_ui(self):
        # Logo / Marca e Botão do GitHub à esquerda
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.pack(side="left", padx=20)

        brand_icon = ctk.CTkLabel(
            brand_frame,
            text="🔻",
            font=("Segoe UI", 18),
            text_color=Theme.PRIMARY
        )
        brand_icon.pack(side="left", padx=(0, 6))

        brand_label = ctk.CTkLabel(
            brand_frame,
            text="NEXUS FETCH",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN
        )
        brand_label.pack(side="left")

        # Botão oficial para o repositório do GitHub (Issues / Feedback)
        self.btn_github = ctk.CTkButton(
            brand_frame,
            text="🐙 GitHub",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.BG_CARD_LIGHT,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_NORMAL,
            border_width=1,
            border_color=Theme.BORDER_SUBTLE,
            height=28,
            width=88,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=lambda: webbrowser.open("https://github.com/PatoDesoxigenado/NexusFetch")
        )
        self.btn_github.pack(side="left", padx=(14, 0))

        # Botões de Navegação e Atualização à direita
        self.nav_buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_buttons_frame.pack(side="right", padx=15)

        # Botão em destaque de atualização do aplicativo (inicialmente oculto)
        self.btn_update = ctk.CTkButton(
            self.nav_buttons_frame,
            text="⚡ Nova Versão",
            font=Theme.FONT_BUTTON,
            fg_color="#059669",
            hover_color="#10B981",
            text_color="#FFFFFF",
            height=36,
            width=175,
            corner_radius=Theme.CORNER_RADIUS_SM
        )

        # Botão alternador de Tema (Claro / Escuro) com ícone centrado e nítido
        curr_mode = ctk.get_appearance_mode().lower()
        self.btn_theme = ctk.CTkButton(
            self.nav_buttons_frame,
            text="",
            image=self.moon_icon if curr_mode == "light" else self.sun_icon,
            width=38,
            height=36,
            fg_color=Theme.BG_CARD_LIGHT,
            hover_color=Theme.SECONDARY_HOVER,
            border_width=1,
            border_color=Theme.BORDER_SUBTLE,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._toggle_theme
        )
        self.btn_theme.pack(side="left", padx=(0, 6))

        for mod_key, mod_info in MODULES.items():
            icon_img = self.platform_icons.get(mod_key)
            label_text = f" {mod_info['label']}" if icon_img else f"{mod_info['icon']}  {mod_info['label']}"
            btn = ctk.CTkButton(
                self.nav_buttons_frame,
                text=label_text,
                image=icon_img,
                compound="left",
                font=Theme.FONT_BUTTON,
                width=135,
                height=36,
                corner_radius=Theme.CORNER_RADIUS_SM,
                command=lambda k=mod_key: self._on_btn_click(k)
            )
            btn.pack(side="left", padx=3)
            self.buttons[mod_key] = btn

        self._update_button_styles()

    def _toggle_theme(self):
        """Alterna dinamicamente entre Tema Claro e Tema Escuro."""
        current_mode = ctk.get_appearance_mode().lower()
        new_mode = "light" if current_mode == "dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self.btn_theme.configure(image=self.moon_icon if new_mode == "light" else self.sun_icon)
        self._update_button_styles()

    def show_update_button(
        self,
        text: str,
        command: Optional[Callable[[], None]] = None,
        fg_color: str = "#059669",
        hover_color: str = "#10B981",
        state: str = "normal"
    ):
        """Exibe o botão de atualização em destaque ao lado das opções."""
        self.btn_update.configure(
            text=text,
            fg_color=fg_color,
            hover_color=hover_color,
            state=state
        )
        if command:
            self.btn_update.configure(command=command)

        if not self.btn_update.winfo_ismapped():
            self.btn_update.pack(side="left", padx=(0, 6), before=self.btn_theme)

    def hide_update_button(self):
        """Oculta o botão de atualização."""
        if self.btn_update.winfo_ismapped():
            self.btn_update.pack_forget()

    def _on_btn_click(self, module_key: str):
        if module_key != self.current_module:
            self.set_active_module(module_key)
            if self.on_module_selected:
                self.on_module_selected(module_key)

    def select_tab_by_index(self, index: int):
        """Alterna para a aba correspondente ao índice numérico (0 a N)."""
        if 0 <= index < len(self.module_keys):
            target_key = self.module_keys[index]
            self._on_btn_click(target_key)

    def set_active_module(self, module_key: str):
        """Atualiza a aba ativa visualmente."""
        self.current_module = module_key
        self._update_button_styles()

    def _update_button_styles(self):
        for mod_key, btn in self.buttons.items():
            is_converter = (mod_key == MODULE_CONVERTER)
            is_active = (mod_key == self.current_module)

            if is_active:
                if is_converter:
                    btn.configure(
                        fg_color=Theme.CONVERTER_PRIMARY,
                        hover_color=Theme.CONVERTER_HOVER,
                        text_color="#FFFFFF",
                        border_width=0
                    )
                else:
                    btn.configure(
                        fg_color=Theme.PRIMARY,
                        hover_color=Theme.PRIMARY_HOVER,
                        text_color="#FFFFFF",
                        border_width=0
                    )
            else:
                if is_converter:
                    btn.configure(
                        fg_color=Theme.CONVERTER_BG_LIGHT,
                        hover_color=Theme.SECONDARY_HOVER,
                        text_color=Theme.CONVERTER_TEXT_BRIGHT,
                        border_width=1,
                        border_color=Theme.CONVERTER_BORDER
                    )
                else:
                    btn.configure(
                        fg_color=Theme.BG_CARD_LIGHT,
                        hover_color=Theme.SECONDARY_HOVER,
                        text_color=Theme.TEXT_NORMAL,
                        border_width=1,
                        border_color=Theme.BORDER_SUBTLE
                    )
