"""Modal de diagnóstico inicial de ambiente e dependências com instalação automática do FFmpeg."""
import threading
import webbrowser
import customtkinter as ctk
from src.ui.theme import Theme
from src.utils.diagnostics import DiagnosticResult, install_ffmpeg_auto, find_ffmpeg

class DiagnosticModal(ctk.CTkToplevel):
    def __init__(self, parent, diag_result: DiagnosticResult, on_continue=None):
        super().__init__(parent)
        self.diag_result = diag_result
        self.on_continue = on_continue

        self.title("Nexus Fetch - Diagnóstico de Sistema")
        self.geometry("540x510")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_DARK)
        self.transient(parent)
        self.grab_set()

        # Centraliza na tela
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 270
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 255
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._build_ui()

    def _build_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=Theme.CORNER_RADIUS, border_width=1, border_color=Theme.BORDER)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho
        title_label = ctk.CTkLabel(
            main_frame,
            text="⚙️ Verificação de Ambiente",
            font=Theme.FONT_TITLE,
            text_color=Theme.TEXT_MAIN
        )
        title_label.pack(pady=(16, 4))

        subtitle_label = ctk.CTkLabel(
            main_frame,
            text="Verificamos os componentes essenciais para o funcionamento do app:",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MUTED
        )
        subtitle_label.pack(pady=(0, 12))

        # Lista de itens
        items_frame = ctk.CTkFrame(main_frame, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        items_frame.pack(fill="x", padx=16, pady=4)

        # 1. FFmpeg
        self.lbl_ffmpeg_status = self._add_status_row(
            items_frame,
            "FFmpeg (Conversor de Áudio/Vídeo):",
            "Instalado" if self.diag_result.ffmpeg_available else "Não Encontrado",
            Theme.SUCCESS if self.diag_result.ffmpeg_available else Theme.DANGER
        )

        # 2. Conexão
        self._add_status_row(
            items_frame,
            "Conexão com a Internet:",
            "Online" if self.diag_result.internet_available else "Sem Conexão",
            Theme.SUCCESS if self.diag_result.internet_available else Theme.WARNING
        )

        # 3. Permissão de Escrita
        self._add_status_row(
            items_frame,
            "Acesso à Pasta de Downloads:",
            "OK" if self.diag_result.write_permission else "Bloqueado",
            Theme.SUCCESS if self.diag_result.write_permission else Theme.DANGER
        )

        # Seção do FFmpeg caso falte
        self.ffmpeg_action_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.ffmpeg_action_container.pack(fill="x", padx=16, pady=10)

        if not self.diag_result.ffmpeg_available:
            self.warn_box = ctk.CTkFrame(self.ffmpeg_action_container, fg_color="#2A1515", corner_radius=Theme.CORNER_RADIUS_SM, border_width=1, border_color="#7F1D1D")
            self.warn_box.pack(fill="x", pady=(0, 8))

            msg = (
                "⚠️ O FFmpeg não foi encontrado no sistema.\n"
                "Para converter músicas em MP3 e mesclar vídeos em alta definição (1080p+),\n"
                "o Nexus Fetch pode baixar e configurar o FFmpeg automaticamente para você."
            )
            self.lbl_warn_msg = ctk.CTkLabel(
                self.warn_box,
                text=msg,
                font=Theme.FONT_SMALL,
                text_color="#FCA5A5",
                justify="left"
            )
            self.lbl_warn_msg.pack(padx=12, pady=8)

            # Barra de progresso da instalação (inicialmente oculta)
            self.install_progress_frame = ctk.CTkFrame(self.ffmpeg_action_container, fg_color="transparent")
            
            self.lbl_install_status = ctk.CTkLabel(
                self.install_progress_frame,
                text="Preparando download...",
                font=Theme.FONT_SMALL,
                text_color=Theme.TEXT_MAIN
            )
            self.lbl_install_status.pack(anchor="w", pady=(0, 4))

            self.install_progress_bar = ctk.CTkProgressBar(
                self.install_progress_frame,
                fg_color=Theme.BG_DARK,
                progress_color=Theme.PRIMARY,
                height=8,
                corner_radius=Theme.CORNER_RADIUS_SM
            )
            self.install_progress_bar.set(0.0)
            self.install_progress_bar.pack(fill="x", pady=(0, 8))

            # Botão de Instalação Automática
            self.btn_auto_install = ctk.CTkButton(
                self.ffmpeg_action_container,
                text="⚡ Baixar e Instalar FFmpeg Automaticamente (1-Clique)",
                fg_color=Theme.PRIMARY,
                hover_color=Theme.PRIMARY_HOVER,
                font=Theme.FONT_BODY_BOLD,
                height=36,
                command=self._start_ffmpeg_auto_install
            )
            self.btn_auto_install.pack(fill="x", pady=(0, 6))

            # Link discreto alternativo para navegador
            self.btn_web_link = ctk.CTkButton(
                self.ffmpeg_action_container,
                text="🌐 Ou abrir site oficial do FFmpeg no navegador",
                fg_color="transparent",
                hover_color=Theme.BG_DARK,
                text_color=Theme.TEXT_MUTED,
                font=Theme.FONT_SMALL,
                height=24,
                command=lambda: webbrowser.open("https://ffmpeg.org/download.html")
            )
            self.btn_web_link.pack()

        # Botão Continuar
        self.btn_continue = ctk.CTkButton(
            main_frame,
            text="Entendido, Continuar para o App",
            fg_color=Theme.SECONDARY if not self.diag_result.ffmpeg_available else Theme.PRIMARY,
            hover_color=Theme.SECONDARY_HOVER if not self.diag_result.ffmpeg_available else Theme.PRIMARY_HOVER,
            font=Theme.FONT_BODY_BOLD,
            height=38,
            command=self._handle_continue
        )
        self.btn_continue.pack(pady=(6, 12))

    def _add_status_row(self, parent, label_text: str, status_text: str, status_color: str) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=7)

        ctk.CTkLabel(
            row,
            text=label_text,
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MAIN
        ).pack(side="left")

        lbl_status = ctk.CTkLabel(
            row,
            text=f"● {status_text}",
            font=Theme.FONT_BODY_BOLD,
            text_color=status_color
        )
        lbl_status.pack(side="right")
        return lbl_status

    def _start_ffmpeg_auto_install(self):
        self.btn_auto_install.configure(state="disabled", text="Instalando FFmpeg...")
        if hasattr(self, "btn_web_link"):
            self.btn_web_link.pack_forget()

        self.install_progress_frame.pack(fill="x", pady=(0, 6))

        def on_prog(percent: float, msg: str):
            self.after(0, lambda: self._update_install_ui(percent, msg))

        def worker():
            success, message = install_ffmpeg_auto(on_progress=on_prog)
            self.after(0, lambda: self._on_install_finished(success, message))

        threading.Thread(target=worker, daemon=True).start()

    def _update_install_ui(self, percent: float, msg: str):
        self.install_progress_bar.set(percent / 100.0)
        self.lbl_install_status.configure(text=msg)

    def _on_install_finished(self, success: bool, message: str):
        if success:
            self.lbl_ffmpeg_status.configure(text="● Instalado", text_color=Theme.SUCCESS)
            self.install_progress_bar.set(1.0)
            self.install_progress_bar.configure(progress_color=Theme.SUCCESS)
            self.lbl_install_status.configure(text=f"✓ {message}", text_color=Theme.SUCCESS)
            
            if hasattr(self, "btn_auto_install"):
                self.btn_auto_install.pack_forget()
            if hasattr(self, "warn_box"):
                self.warn_box.pack_forget()

            self.btn_continue.configure(
                text="Continuar para o Nexus Fetch",
                fg_color=Theme.PRIMARY,
                hover_color=Theme.PRIMARY_HOVER
            )
            # Continua automaticamente após 1.5s
            self.after(1500, self._handle_continue)
        else:
            self.install_progress_bar.configure(progress_color=Theme.DANGER)
            self.lbl_install_status.configure(text=f"✖ {message}", text_color=Theme.DANGER)
            self.btn_auto_install.configure(state="normal", text="Tentar Novamente")

    def _handle_continue(self):
        self.destroy()
        if self.on_continue:
            self.on_continue()
