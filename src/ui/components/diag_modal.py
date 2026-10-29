"""Modal de diagnóstico inicial de ambiente e dependências."""
import webbrowser
import customtkinter as ctk
from src.ui.theme import Theme
from src.utils.diagnostics import DiagnosticResult

class DiagnosticModal(ctk.CTkToplevel):
    def __init__(self, parent, diag_result: DiagnosticResult, on_continue=None):
        super().__init__(parent)
        self.diag_result = diag_result
        self.on_continue = on_continue

        self.title("Nexus Fetch - Diagnóstico de Sistema")
        self.geometry("520x440")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_DARK)
        self.transient(parent)
        self.grab_set()

        # Centraliza na tela
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 260
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 220
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
        title_label.pack(pady=(20, 5))

        subtitle_label = ctk.CTkLabel(
            main_frame,
            text="Verificamos os componentes essenciais para o funcionamento do app:",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MUTED
        )
        subtitle_label.pack(pady=(0, 15))

        # Lista de itens
        items_frame = ctk.CTkFrame(main_frame, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        items_frame.pack(fill="x", padx=20, pady=5)

        # 1. FFmpeg
        self._add_status_row(
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

        # Mensagem explicativa se faltar FFmpeg
        if not self.diag_result.ffmpeg_available:
            warn_box = ctk.CTkFrame(main_frame, fg_color="#2A1515", corner_radius=Theme.CORNER_RADIUS_SM, border_width=1, border_color="#7F1D1D")
            warn_box.pack(fill="x", padx=20, pady=15)

            msg = (
                "⚠️ O FFmpeg não foi encontrado no PATH do sistema.\n"
                "Downloads diretos ainda funcionam, porém a conversão de MP3\n"
                "e mesclagem de vídeos em 1080p+ necessitam do FFmpeg."
            )
            ctk.CTkLabel(
                warn_box,
                text=msg,
                font=Theme.FONT_SMALL,
                text_color="#FCA5A5",
                justify="left"
            ).pack(padx=12, pady=10)

            # Botão para baixar FFmpeg
            btn_ffmpeg = ctk.CTkButton(
                main_frame,
                text="🌐 Baixar FFmpeg Oficial",
                fg_color=Theme.SECONDARY,
                hover_color=Theme.SECONDARY_HOVER,
                font=Theme.FONT_BODY_BOLD,
                command=lambda: webbrowser.open("https://ffmpeg.org/download.html")
            )
            btn_ffmpeg.pack(pady=(0, 10))

        # Botão Continuar
        btn_continue = ctk.CTkButton(
            main_frame,
            text="Entendido, Continuar para o App",
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.FONT_BODY_BOLD,
            height=38,
            command=self._handle_continue
        )
        btn_continue.pack(pady=(10, 15))

    def _add_status_row(self, parent, label_text: str, status_text: str, status_color: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=8)

        ctk.CTkLabel(
            row,
            text=label_text,
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MAIN
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text=f"● {status_text}",
            font=Theme.FONT_BODY_BOLD,
            text_color=status_color
        ).pack(side="right")

    def _handle_continue(self):
        self.destroy()
        if self.on_continue:
            self.on_continue()
