"""Barra superior de navegação entre plataformas com atalho do GitHub e alerta de atualização."""
import webbrowser
from typing import Callable, Dict, Optional
import customtkinter as ctk
from src.ui.theme import Theme
from src.config import MODULES, MODULE_YOUTUBE

class NavBar(ctk.CTkFrame):
    def __init__(self, parent, on_module_selected: Callable[[str], None]):
        super().__init__(parent, fg_color=Theme.BG_CARD, height=60, corner_radius=Theme.CORNER_RADIUS, border_width=1, border_color=Theme.BORDER)
        self.pack_propagate(False)
        self.on_module_selected = on_module_selected
        self.current_module = MODULE_YOUTUBE
        self.buttons: Dict[str, ctk.CTkButton] = {}

        self._build_ui()

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
            font=("Segoe UI", 16, "bold"),
            text_color=Theme.TEXT_MAIN
        )
        brand_label.pack(side="left")

        # Botão oficial para o repositório do GitHub (Issues / Feedback)
        self.btn_github = ctk.CTkButton(
            brand_frame,
            text="🐙 GitHub",
            font=Theme.FONT_SMALL,
            fg_color="transparent",
            hover_color=Theme.BG_DARK,
            text_color=Theme.TEXT_MUTED,
            border_width=1,
            border_color=Theme.BORDER,
            height=26,
            width=84,
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
            font=Theme.FONT_BODY_BOLD,
            fg_color="#059669",
            hover_color="#10B981",
            text_color="#FFFFFF",
            height=36,
            width=175,
            corner_radius=Theme.CORNER_RADIUS_SM
        )

        for mod_key, mod_info in MODULES.items():
            btn = ctk.CTkButton(
                self.nav_buttons_frame,
                text=f"{mod_info['icon']}  {mod_info['label']}",
                font=Theme.FONT_BODY_BOLD,
                width=130,
                height=36,
                corner_radius=Theme.CORNER_RADIUS_SM,
                command=lambda k=mod_key: self._on_btn_click(k)
            )
            btn.pack(side="left", padx=4)
            self.buttons[mod_key] = btn

        self._update_button_styles()

    def show_update_button(
        self,
        text: str,
        command: Optional[Callable[[], None]] = None,
        fg_color: str = "#059669",
        hover_color: str = "#10B981",
        state: str = "normal"
    ):
        """Exibe o botão de atualização em destaque exatamente ao lado do módulo YouTube."""
        self.btn_update.configure(
            text=text,
            fg_color=fg_color,
            hover_color=hover_color,
            state=state
        )
        if command:
            self.btn_update.configure(command=command)

        yt_button = self.buttons.get(MODULE_YOUTUBE)
        if yt_button and not self.btn_update.winfo_ismapped():
            self.btn_update.pack(side="left", padx=(0, 8), before=yt_button)

    def hide_update_button(self):
        """Oculta o botão de atualização."""
        if self.btn_update.winfo_ismapped():
            self.btn_update.pack_forget()

    def _on_btn_click(self, module_key: str):
        if module_key != self.current_module:
            self.set_active_module(module_key)
            if self.on_module_selected:
                self.on_module_selected(module_key)

    def set_active_module(self, module_key: str):
        """Atualiza a aba ativa visualmente."""
        self.current_module = module_key
        self._update_button_styles()

    def _update_button_styles(self):
        for mod_key, btn in self.buttons.items():
            if mod_key == self.current_module:
                btn.configure(
                    fg_color=Theme.PRIMARY,
                    hover_color=Theme.PRIMARY_HOVER,
                    text_color=Theme.TEXT_MAIN
                )
            else:
                btn.configure(
                    fg_color=Theme.SECONDARY,
                    hover_color=Theme.SECONDARY_HOVER,
                    text_color=Theme.TEXT_MUTED
                )
