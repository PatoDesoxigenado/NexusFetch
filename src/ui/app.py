"""Janela principal do Nexus Fetch com fila de mensagens (Queue) 100% thread-safe."""
import os
import queue
import threading
from typing import Optional
import customtkinter as ctk
from PIL import Image

from src.config import (
    APP_NAME,
    APP_VERSION,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    MODULE_YOUTUBE,
    ICON_ICO_PATH,
    ICON_PNG_PATH,
)
from src.ui.theme import Theme
from src.ui.components.navbar import NavBar
from src.ui.components.url_input import UrlInputBar
from src.ui.components.preview import MediaPreviewCard
from src.ui.components.format_bar import FormatSelectionBar
from src.ui.components.progress import DownloadActionSection
from src.ui.components.diag_modal import DiagnosticModal

from src.utils.diagnostics import run_startup_diagnostics, DiagnosticResult
from src.core.metadata import extract_media_info, MediaMetadata, clear_thumbnail_cache
from src.core.downloader import MediaDownloader
from src.utils.logger import log_info, log_error

class NexusFetchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=Theme.BG_DARK)

        # Fila de comunicação Thread-Safe
        self.ui_queue = queue.Queue()
        self._poll_ui_queue()

        # Ícone da Janela
        self._set_window_icon()

        # Estado da Aplicação
        self.active_module = MODULE_YOUTUBE
        self.current_metadata: Optional[MediaMetadata] = None
        self.downloader = MediaDownloader()
        self.diag_result: Optional[DiagnosticResult] = None

        # Construção da Interface
        self._build_ui()

        # Executa a rotina de diagnóstico de inicialização
        self.after(200, self._perform_startup_check)

    def run_on_ui(self, func, *args):
        """Agrega chamadas à fila thread-safe para execução na thread principal do Tkinter."""
        self.ui_queue.put((func, args))

    def _poll_ui_queue(self):
        """Processa todas as mensagens pendentes na thread do Tkinter sem bloquear."""
        try:
            while True:
                func, args = self.ui_queue.get_nowait()
                try:
                    func(*args)
                except Exception as e:
                    log_error(f"Erro ao executar callback na UI: {e}")
        except queue.Empty:
            pass
        self.after(40, self._poll_ui_queue)

    def _set_window_icon(self):
        try:
            if os.path.exists(ICON_ICO_PATH):
                self.iconbitmap(ICON_ICO_PATH)
            elif os.path.exists(ICON_PNG_PATH):
                icon_img = Image.open(ICON_PNG_PATH)
                from PIL import ImageTk
                tk_icon = ImageTk.PhotoImage(icon_img)
                self.wm_iconphoto(True, tk_icon)
        except Exception:
            pass

    def _build_ui(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=24, pady=18)

        # 1. Topo: Barra de Navegação (Fixa no topo)
        self.navbar = NavBar(
            self.main_container,
            on_module_selected=self._on_module_changed
        )
        self.navbar.pack(side="top", fill="x", pady=(0, 12))

        # 2. Rodapé: Barra de Progresso e Botão BAIXAR (Ancorada permanentemente)
        self.action_section = DownloadActionSection(
            self.main_container,
            on_start_download=self._start_download,
            on_cancel_download=self._cancel_download
        )
        self.action_section.pack(side="bottom", fill="x", pady=(12, 0))

        # 3. Centro: Container Principal com rolagem suave
        self.scroll_area = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="transparent",
            scrollbar_button_color=Theme.SECONDARY,
            scrollbar_button_hover_color=Theme.SECONDARY_HOVER
        )
        self.scroll_area.pack(side="top", fill="both", expand=True)

        # 3.1 Campo de Entrada de URL
        self.url_bar = UrlInputBar(
            self.scroll_area,
            on_analyze=self._on_analyze_url,
            on_cross_redirect=self._on_cross_redirect
        )
        self.url_bar.pack(fill="x", pady=(0, 10))

        # 3.2 Card de Boas-vindas (Exibido no estado inicial colado à barra de URL)
        self.welcome_card = ctk.CTkFrame(
            self.scroll_area,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.welcome_card.pack(fill="x", pady=(0, 10))

        w_content = ctk.CTkFrame(self.welcome_card, fg_color="transparent")
        w_content.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            w_content,
            text="Pronto para Baixar suas Mídias",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            w_content,
            text="Cole o link do YouTube, Twitter/X ou Instagram acima e clique em 'Analisar' para ver a prévia e opções de download.",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MUTED
        ).pack(anchor="w", pady=(0, 12))

        pills_row = ctk.CTkFrame(w_content, fg_color="transparent")
        pills_row.pack(anchor="w")

        self._add_badge(pills_row, "▶ YouTube (Vídeos até 4K e Áudio MP3 320kbps)")
        self._add_badge(pills_row, "📸 Instagram (Reels e Fotos)")
        self._add_badge(pills_row, "✖ Twitter / X (Vídeos, GIFs e Fotos HD)")

        # 3.3 Card de Preview da Mídia (Oculto inicialmente até analisar o primeiro link)
        self.preview_card = MediaPreviewCard(
            self.scroll_area,
            on_status_message=self._show_temp_status,
            app_instance=self
        )

        # 3.4 Barra de Seleção de Formato e Pasta (Oculta inicialmente até analisar o primeiro link)
        self.format_bar = FormatSelectionBar(
            self.scroll_area,
            on_options_changed=self._on_format_options_changed
        )

    def _add_badge(self, parent, text: str):
        badge = ctk.CTkFrame(parent, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        badge.pack(side="left", padx=(0, 8), pady=2)
        ctk.CTkLabel(
            badge,
            text=text,
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MUTED
        ).pack(padx=10, pady=4)

    def _perform_startup_check(self):
        """Executa a checagem das bibliotecas e ambiente ao abrir o app."""
        self.diag_result = run_startup_diagnostics()
        if not self.diag_result.ffmpeg_available or not self.diag_result.write_permission:
            DiagnosticModal(self, self.diag_result)

    def _on_module_changed(self, module_key: str):
        self.active_module = module_key
        self.url_bar.set_current_module(module_key)

    def _on_cross_redirect(self, target_module: str, url: str):
        """Muda para a aba correta e dispara a análise automaticamente."""
        self.navbar.set_active_module(target_module)
        self.active_module = target_module
        self.url_bar.set_current_module(target_module)
        self.url_bar.set_url(url)
        self._on_analyze_url(url)

    def _on_analyze_url(self, url: str):
        """Dispara a extração de metadados em thread separada com limpeza completa."""
        clear_thumbnail_cache()
        self.url_bar.set_loading(True)

        def worker():
            metadata = None
            try:
                metadata = extract_media_info(url)
            except Exception as e:
                log_error("Erro fatal ao extrair mídia", e)
                metadata = MediaMetadata(
                    url=url,
                    title="Erro ao processar link",
                    uploader="Desconhecido",
                    duration=0,
                    duration_str="--:--",
                    thumbnail_url=None,
                    error=f"Falha na extração de dados: {str(e)[:100]}"
                )
            finally:
                # 100% garantido na fila da thread principal
                self.run_on_ui(self._on_metadata_received, metadata)

        threading.Thread(target=worker, daemon=True).start()

    def _on_metadata_received(self, metadata: Optional[MediaMetadata]):
        self.url_bar.set_loading(False)

        if not metadata:
            self.url_bar.show_error("Não foi possível carregar os dados deste link.")
            return

        self.current_metadata = metadata

        if metadata.error:
            self.url_bar.show_error(metadata.error)
            return

        # Oculta o card de boas-vindas e exibe os cards reais da mídia
        if self.welcome_card.winfo_ismapped():
            self.welcome_card.pack_forget()

        if not self.preview_card.winfo_ismapped():
            self.preview_card.pack(fill="x", pady=(0, 10))

        if not self.format_bar.winfo_ismapped():
            self.format_bar.pack(fill="x", pady=(0, 4))

        # Atualiza prévia e opções
        self.preview_card.display_metadata(metadata)
        self.format_bar.configure_for_media(metadata)
        self.action_section.show_ready_state()

    def _on_format_options_changed(self):
        pass

    def _start_download(self):
        if not self.current_metadata or not self.current_metadata.url:
            self.url_bar.show_error("Nenhuma mídia selecionada para download.")
            return

        mode, format_id, output_dir = self.format_bar.get_selected_options()

        self.action_section.set_downloading_state()

        def on_prog(percent, speed_str, eta_str, filename):
            self.run_on_ui(self.action_section.update_progress, percent, speed_str, eta_str, filename)

        def on_stat(msg):
            self.run_on_ui(self.action_section.set_status_message, msg)

        def on_done(success, msg, path):
            self.run_on_ui(self.action_section.set_completed_state, success, msg, path)

        self.downloader.download_async(
            url=self.current_metadata.url,
            output_dir=output_dir,
            mode=mode,
            format_id=format_id,
            media_type=self.current_metadata.media_type,
            image_urls=self.current_metadata.image_urls,
            title=self.current_metadata.title,
            on_progress=on_prog,
            on_status=on_stat,
            on_complete=on_done
        )

    def _cancel_download(self):
        self.downloader.cancel()
        self.action_section.set_status_message("Cancelando download...")

    def _show_temp_status(self, message: str, status_type: str = "info"):
        self.action_section.set_status_message(message)
