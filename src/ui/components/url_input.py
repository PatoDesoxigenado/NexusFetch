"""Barra de entrada de URL com feedback dinâmico sem vácuo visual."""
from typing import Callable, Optional
import customtkinter as ctk
from src.ui.theme import Theme
from src.utils.validators import validate_url, ValidationStatus, ValidationResult

class UrlInputBar(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_analyze: Callable[[str], None],
        on_cross_redirect: Callable[[str, str], None]
    ):
        super().__init__(parent, fg_color="transparent")
        self.on_analyze = on_analyze
        self.on_cross_redirect = on_cross_redirect
        self.current_module = "youtube"

        self._build_ui()

    def _build_ui(self):
        # Container da linha de entrada
        self.input_row = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.input_row.pack(fill="x")

        # Campo de entrada
        self.entry_url = ctk.CTkEntry(
            self.input_row,
            placeholder_text="Cole o link da mídia aqui (ex: https://www.youtube.com/watch?v=...)",
            placeholder_text_color=Theme.TEXT_DIM,
            font=Theme.FONT_BODY,
            fg_color="transparent",
            border_width=0,
            text_color=Theme.TEXT_MAIN,
            height=44
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(15, 8), pady=4)
        self.entry_url.bind("<Return>", lambda event: self._on_confirm_click())

        # Botão Colar
        self.btn_paste = ctk.CTkButton(
            self.input_row,
            text="📋 Colar",
            width=75,
            height=34,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            font=Theme.FONT_SMALL,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_paste_click
        )
        self.btn_paste.pack(side="left", padx=(0, 6))

        # Botão Analisar
        self.btn_analyze = ctk.CTkButton(
            self.input_row,
            text="🔍 Analisar",
            width=110,
            height=34,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.FONT_BODY_BOLD,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_confirm_click
        )
        self.btn_analyze.pack(side="left", padx=(0, 10))

        # Container para mensagens de erro / aviso cruzado (NÃO empacotado inicialmente para evitar vácuo)
        self.feedback_container = ctk.CTkFrame(self, fg_color="transparent")

    def set_current_module(self, module_key: str):
        self.current_module = module_key
        self.clear_feedback()

    def get_url(self) -> str:
        return self.entry_url.get().strip()

    def set_url(self, url: str):
        self.entry_url.delete(0, "end")
        self.entry_url.insert(0, url)

    def set_loading(self, is_loading: bool):
        if is_loading:
            self.btn_analyze.configure(text="⏳ Buscando...", state="disabled", fg_color=Theme.SECONDARY)
            self.btn_paste.configure(state="disabled")
        else:
            self.btn_analyze.configure(text="🔍 Analisar", state="normal", fg_color=Theme.PRIMARY)
            self.btn_paste.configure(state="normal")

    def _on_paste_click(self):
        try:
            clipboard = self.clipboard_get().strip()
            if clipboard:
                self.set_url(clipboard)
                self.clear_feedback()
                self._on_confirm_click()
        except Exception:
            pass

    def _on_confirm_click(self):
        url = self.get_url()
        self.clear_feedback()

        if not url:
            self.show_error("Por favor, cole um link antes de analisar.")
            return

        result = validate_url(url, self.current_module)

        if result.status == ValidationStatus.VALID:
            if self.on_analyze:
                self.on_analyze(result.url)

        elif result.status == ValidationStatus.CROSS_MATCH:
            self.show_cross_match_banner(result)

        else:
            self.show_error(result.message or "Link inválido ou não suportado.")

    def show_cross_match_banner(self, result: ValidationResult):
        """Exibe banner interativo quando o link pertence a outro módulo."""
        self.clear_feedback()
        self.feedback_container.pack(fill="x", pady=(6, 0))

        banner = ctk.CTkFrame(
            self.feedback_container,
            fg_color="#182333",
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color="#1E3A8A"
        )
        banner.pack(fill="x")

        content_frame = ctk.CTkFrame(banner, fg_color="transparent")
        content_frame.pack(fill="x", padx=12, pady=8)

        msg_label = ctk.CTkLabel(
            content_frame,
            text=f"💡 Este link não é válido aqui, mas pertence à aba \"{result.suggested_label}\".",
            font=Theme.FONT_BODY,
            text_color="#93C5FD",
            justify="left"
        )
        msg_label.pack(side="left", padx=(0, 10))

        btn_redirect = ctk.CTkButton(
            content_frame,
            text=f"Ir para {result.suggested_label} e Analisar ➜",
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.FONT_BODY_BOLD,
            height=30,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=lambda: self._trigger_cross_redirect(result.suggested_module, result.url)
        )
        btn_redirect.pack(side="right")

    def _trigger_cross_redirect(self, target_module: Optional[str], url: str):
        self.clear_feedback()
        if target_module and self.on_cross_redirect:
            self.on_cross_redirect(target_module, url)

    def show_error(self, message: str):
        self.clear_feedback()
        self.feedback_container.pack(fill="x", pady=(4, 0))
        lbl = ctk.CTkLabel(
            self.feedback_container,
            text=f"⚠️ {message}",
            font=Theme.FONT_SMALL,
            text_color=Theme.DANGER
        )
        lbl.pack(anchor="w", padx=4, pady=(2, 0))

    def clear_feedback(self):
        for widget in self.feedback_container.winfo_children():
            widget.destroy()
        if self.feedback_container.winfo_ismapped():
            self.feedback_container.pack_forget()
