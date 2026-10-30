"""Barra de progresso, métricas e botão inteligente de download."""
import os
import subprocess
from typing import Callable, Optional
import customtkinter as ctk
from src.ui.theme import Theme

class DownloadActionSection(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_start_download: Callable[[], None],
        on_cancel_download: Callable[[], None]
    ):
        super().__init__(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.on_start_download = on_start_download
        self.on_cancel_download = on_cancel_download
        self.downloaded_path = ""

        self._build_ui()

    def _build_ui(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=16, pady=16)

        # 1. Informações de Status e Métricas
        self.info_row = ctk.CTkFrame(self.container, fg_color="transparent")
        self.info_row.pack(fill="x", pady=(0, 8))

        self.lbl_status = ctk.CTkLabel(
            self.info_row,
            text="Pronto para baixar",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_status.pack(side="left")

        self.metrics_frame = ctk.CTkFrame(self.info_row, fg_color="transparent")
        self.metrics_frame.pack(side="right")

        self.lbl_speed = ctk.CTkLabel(
            self.metrics_frame,
            text="",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_speed.pack(side="left", padx=(0, 12))

        self.lbl_eta = ctk.CTkLabel(
            self.metrics_frame,
            text="",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_eta.pack(side="left")

        # 2. Barra de Progresso
        self.progress_bar = ctk.CTkProgressBar(
            self.container,
            fg_color=Theme.BG_DARK,
            progress_color=Theme.PRIMARY,
            height=10,
            corner_radius=Theme.CORNER_RADIUS_SM
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(0, 12))

        # 3. Linha de Botões de Ação
        self.action_row = ctk.CTkFrame(self.container, fg_color="transparent")
        self.action_row.pack(fill="x")

        # Botão Cancelar (oculto por padrão)
        self.btn_cancel = ctk.CTkButton(
            self.action_row,
            text="✖ Cancelar",
            fg_color="#374151",
            hover_color="#4B5563",
            font=Theme.FONT_BODY,
            width=100,
            height=40,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_cancel_click
        )

        # Botão Abrir Pasta (oculto por padrão)
        self.btn_open_folder = ctk.CTkButton(
            self.action_row,
            text="📂 Abrir Pasta",
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            font=Theme.FONT_BODY_BOLD,
            width=130,
            height=40,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_open_folder_click
        )

        # Botão Principal Inteligente: BAIXAR
        self.btn_download = ctk.CTkButton(
            self.action_row,
            text="⚡ BAIXAR AGORA",
            font=Theme.FONT_TITLE,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            height=44,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_download_click
        )
        self.btn_download.pack(side="right", fill="x", expand=True)

    def show_ready_state(self, custom_text: Optional[str] = None):
        """Ativa e destaca o botão BAIXAR quando a mídia for reconhecida."""
        self.progress_bar.set(0.0)
        self.progress_bar.configure(progress_color=Theme.PRIMARY)
        self.lbl_status.configure(text="Pronto para baixar", text_color=Theme.TEXT_MAIN)
        self.lbl_speed.configure(text="")
        self.lbl_eta.configure(text="")
        self.btn_cancel.pack_forget()
        self.btn_open_folder.pack_forget()
        self.btn_download.pack(side="right", fill="x", expand=True)
        btn_text = custom_text or "⚡ BAIXAR AGORA"
        self.btn_download.configure(state="normal", text=btn_text, fg_color=Theme.PRIMARY)

    def set_download_button_text(self, text: str, enabled: bool = True):
        """Permite customizar o texto e estado do botão de download (ex: para seleção de playlist)."""
        self.btn_download.configure(
            text=text,
            state="normal" if enabled else "disabled",
            fg_color=Theme.PRIMARY if enabled else "#374151"
        )

    def set_downloading_state(self):
        """Atualiza a UI para o estado de download ativo."""
        self.progress_bar.set(0.0)
        self.lbl_status.configure(text="Iniciando download...", text_color=Theme.TEXT_MAIN)
        self.btn_download.configure(state="disabled", text="Baixando...", fg_color=Theme.SECONDARY)
        self.btn_open_folder.pack_forget()
        self.btn_cancel.pack(side="left", padx=(0, 10))

    def update_progress(self, percent: float, speed_str: str, eta_str: str, filename: str):
        """Atualiza porcentagem, velocidade e tempo restante."""
        self.progress_bar.set(percent / 100.0)
        self.lbl_status.configure(text=f"Baixando: {percent:.1f}%")
        self.lbl_speed.configure(text=speed_str)
        self.lbl_eta.configure(text=eta_str)

    def set_status_message(self, message: str):
        self.lbl_status.configure(text=message)

    def set_completed_state(self, success: bool, message: str, file_path: str):
        """Finaliza o estado com feedback de sucesso ou erro."""
        self.btn_cancel.pack_forget()
        self.downloaded_path = file_path

        if success:
            self.progress_bar.set(1.0)
            self.progress_bar.configure(progress_color=Theme.SUCCESS)
            self.lbl_status.configure(text=f"✓ {message}", text_color=Theme.SUCCESS)
            self.lbl_speed.configure(text="")
            self.lbl_eta.configure(text="")
            self.btn_download.configure(state="normal", text="⚡ Baixar Outro", fg_color=Theme.PRIMARY)
            if file_path:
                self.btn_open_folder.pack(side="left", padx=(0, 10))
        else:
            self.progress_bar.configure(progress_color=Theme.DANGER)
            self.lbl_status.configure(text=f"✖ {message}", text_color=Theme.DANGER)
            self.btn_download.configure(state="normal", text="Tentar Novamente", fg_color=Theme.PRIMARY)

    def _on_download_click(self):
        if self.on_start_download:
            self.on_start_download()

    def _on_cancel_click(self):
        if self.on_cancel_download:
            self.on_cancel_download()

    def _on_open_folder_click(self):
        if not self.downloaded_path:
            return
        target_dir = self.downloaded_path if os.path.isdir(self.downloaded_path) else os.path.dirname(self.downloaded_path)
        if os.path.exists(target_dir):
            if os.name == 'nt':
                os.startfile(target_dir)
            else:
                subprocess.run(['xdg-open', target_dir])
