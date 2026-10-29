"""Barra superior de navegação entre plataformas."""
from typing import Callable, Dict
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
        # Logo / Marca à esquerda
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

        # Botões das plataformas à direita
        nav_buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_buttons_frame.pack(side="right", padx=15)

        for mod_key, mod_info in MODULES.items():
            btn = ctk.CTkButton(
                nav_buttons_frame,
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
