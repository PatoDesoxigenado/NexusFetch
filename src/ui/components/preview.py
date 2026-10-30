"""Card de visualização de metadados da mídia (Vídeo único ou Playlist paginada) com Queue Thread-Safe."""
import os
import io
import ssl
import urllib.request
import threading
import tempfile
from typing import Optional, Callable, List
from PIL import Image
import customtkinter as ctk
from src.ui.theme import Theme
from src.core.metadata import MediaMetadata, PlaylistItem, download_thumbnail_image, extract_frame_with_ffmpeg, get_ssl_context
from src.utils.helpers import sanitize_filename
from src.utils.logger import log_info, log_error, log_warning

PAGE_SIZE = 30

class MediaPreviewCard(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_status_message: Optional[Callable[[str, str], None]] = None,
        on_selection_changed: Optional[Callable[[int, int], None]] = None,
        app_instance=None
    ):
        super().__init__(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.on_status_message = on_status_message
        self.on_selection_changed = on_selection_changed
        self.app_instance = app_instance
        self.current_metadata: Optional[MediaMetadata] = None
        self.thumb_image: Optional[ctk.CTkImage] = None
        self.playlist_thumb_image: Optional[ctk.CTkImage] = None
        self._current_load_id = 0
        self.playlist_current_page = 0

        self._build_ui()

    def _safe_ui_dispatch(self, func, *args):
        """Despacha chamada para a thread da interface via run_on_ui ou fallback."""
        if self.app_instance and hasattr(self.app_instance, "run_on_ui"):
            self.app_instance.run_on_ui(func, *args)
        else:
            self.after(0, lambda: func(*args))

    def _build_ui(self):
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # -----------------------------------------------------------------
        # 1. VIEW PARA MÍDIA INDIVIDUAL (Vídeo, Áudio, Foto ou GIF)
        # -----------------------------------------------------------------
        self.single_view = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.single_view.pack(fill="both", expand=True)

        # 1.1 Coluna Esquerda: Thumbnail
        self.thumb_container = ctk.CTkFrame(
            self.single_view,
            fg_color=Theme.BG_DARK,
            width=230,
            height=130,
            corner_radius=Theme.CORNER_RADIUS_SM
        )
        self.thumb_container.pack_propagate(False)
        self.thumb_container.pack(side="left", padx=(0, 16))

        self.thumb_label = ctk.CTkLabel(
            self.thumb_container,
            text="Sem Prévia",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_DIM
        )
        self.thumb_label.pack(fill="both", expand=True)

        # 1.2 Coluna Direita: Informações
        self.info_container = ctk.CTkFrame(self.single_view, fg_color="transparent")
        self.info_container.pack(side="left", fill="both", expand=True)

        self.lbl_title = ctk.CTkLabel(
            self.info_container,
            text="Nenhuma mídia carregada",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN,
            justify="left",
            anchor="w",
            wraplength=480
        )
        self.lbl_title.pack(fill="x", pady=(0, 6))

        meta_row = ctk.CTkFrame(self.info_container, fg_color="transparent")
        meta_row.pack(fill="x", pady=(0, 10))

        self.lbl_uploader = ctk.CTkLabel(
            meta_row,
            text="👤 --",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_uploader.pack(side="left", padx=(0, 15))

        self.lbl_duration = ctk.CTkLabel(
            meta_row,
            text="⏱️ --:--",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_duration.pack(side="left")

        action_row = ctk.CTkFrame(self.info_container, fg_color="transparent")
        action_row.pack(fill="x", side="bottom")

        self.btn_download_thumb = ctk.CTkButton(
            action_row,
            text="📥 Baixar Thumbnail HD",
            font=Theme.FONT_SMALL,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            height=28,
            width=165,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_download_thumb_click
        )
        self.btn_download_thumb.pack(side="left")

        # -----------------------------------------------------------------
        # 2. VIEW PARA PLAYLISTS (YouTube) COM ROLAGEM E PAGINAÇÃO
        # -----------------------------------------------------------------
        self.playlist_view = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        # Cabeçalho da Playlist
        self.pl_header = ctk.CTkFrame(self.playlist_view, fg_color="transparent")
        self.pl_header.pack(fill="x", pady=(0, 10))

        # Miniatura da Playlist
        self.pl_thumb_container = ctk.CTkFrame(
            self.pl_header,
            fg_color=Theme.BG_DARK,
            width=140,
            height=85,
            corner_radius=Theme.CORNER_RADIUS_SM
        )
        self.pl_thumb_container.pack_propagate(False)
        self.pl_thumb_container.pack(side="left", padx=(0, 14))

        self.pl_thumb_label = ctk.CTkLabel(
            self.pl_thumb_container,
            text="📁 Playlist",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_DIM
        )
        self.pl_thumb_label.pack(fill="both", expand=True)

        # Informações da Playlist
        self.pl_info_box = ctk.CTkFrame(self.pl_header, fg_color="transparent")
        self.pl_info_box.pack(side="left", fill="both", expand=True)

        self.lbl_pl_title = ctk.CTkLabel(
            self.pl_info_box,
            text="Título da Playlist",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN,
            justify="left",
            anchor="w",
            wraplength=480
        )
        self.lbl_pl_title.pack(fill="x", pady=(0, 4))

        self.lbl_pl_meta = ctk.CTkLabel(
            self.pl_info_box,
            text="👤 Autor • 0 vídeos",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MUTED,
            anchor="w"
        )
        self.lbl_pl_meta.pack(fill="x", pady=(0, 6))

        # Linha com Botões Rápidos e Badge de Selecionados
        self.pl_ctrl_row = ctk.CTkFrame(self.pl_info_box, fg_color="transparent")
        self.pl_ctrl_row.pack(fill="x")

        self.lbl_pl_selected_count = ctk.CTkLabel(
            self.pl_ctrl_row,
            text="0 de 0 selecionados",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MAIN
        )
        self.lbl_pl_selected_count.pack(side="left", padx=(0, 14))

        self.btn_select_all = ctk.CTkButton(
            self.pl_ctrl_row,
            text="☑️ Marcar Todos",
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            hover_color=Theme.SECONDARY_HOVER,
            height=26,
            width=110,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._select_all_playlist_items
        )
        self.btn_select_all.pack(side="left", padx=(0, 6))

        self.btn_deselect_all = ctk.CTkButton(
            self.pl_ctrl_row,
            text="⬜ Desmarcar Todos",
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            hover_color=Theme.SECONDARY_HOVER,
            height=26,
            width=120,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._deselect_all_playlist_items
        )
        self.btn_deselect_all.pack(side="left")

        # Barra de Navegação de Páginas (Páginas de 30 itens)
        self.pl_pagination_bar = ctk.CTkFrame(self.playlist_view, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        self.pl_pagination_bar.pack(fill="x", pady=(0, 6), padx=2)

        self.btn_prev_page = ctk.CTkButton(
            self.pl_pagination_bar,
            text="◀ Anterior",
            font=Theme.FONT_SMALL,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            height=26,
            width=85,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._prev_page
        )
        self.btn_prev_page.pack(side="left", padx=8, pady=4)

        self.lbl_page_info = ctk.CTkLabel(
            self.pl_pagination_bar,
            text="Página 1 de 1 (Vídeos 1 a 30 de 30)",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MAIN
        )
        self.lbl_page_info.pack(side="left", expand=True)

        self.btn_next_page = ctk.CTkButton(
            self.pl_pagination_bar,
            text="Próxima ▶",
            font=Theme.FONT_SMALL,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            height=26,
            width=85,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._next_page
        )
        self.btn_next_page.pack(side="right", padx=8, pady=4)

        # Lista com rolagem para os 30 vídeos da página
        self.pl_scroll_area = ctk.CTkScrollableFrame(
            self.playlist_view,
            fg_color=Theme.BG_DARK,
            corner_radius=Theme.CORNER_RADIUS_SM,
            height=240,
            scrollbar_button_color=Theme.SECONDARY,
            scrollbar_button_hover_color=Theme.SECONDARY_HOVER
        )
        self.pl_scroll_area.pack(fill="both", expand=True)

    def reset_to_empty(self):
        """Limpa completamente o card cancelando threads pendentes."""
        self._current_load_id += 1
        self.current_metadata = None
        self.playlist_view.pack_forget()
        self.single_view.pack(fill="both", expand=True)

        self._set_placeholder_thumb("Aguardando link...")
        self.lbl_title.configure(text="Aguardando mídia para análise")
        self.lbl_uploader.configure(text="👤 --")
        self.lbl_duration.configure(text="⏱️ --:--")
        self.btn_download_thumb.configure(text="📥 Baixar Thumbnail HD", state="disabled")

    def display_metadata(self, metadata: MediaMetadata):
        """Atualiza o card com os dados da mídia ou playlist."""
        self._current_load_id += 1
        load_id = self._current_load_id
        self.current_metadata = metadata

        if metadata.is_playlist:
            self._display_playlist_view(metadata, load_id)
        else:
            self._display_single_view(metadata, load_id)

    def _display_single_view(self, metadata: MediaMetadata, load_id: int):
        self.playlist_view.pack_forget()
        self.single_view.pack(fill="both", expand=True)

        self.lbl_title.configure(text=metadata.title)
        self.lbl_uploader.configure(text=f"👤 {metadata.uploader}")
        self.lbl_duration.configure(text=f"⏱️ {metadata.duration_str}")

        if metadata.media_type == "image":
            self.btn_download_thumb.configure(text="📥 Salvar Foto HD", state="normal")
        else:
            self.btn_download_thumb.configure(text="📥 Baixar Thumbnail HD", state="normal")

        # 1. Arquivo local
        if metadata.thumbnail_local_path and os.path.exists(metadata.thumbnail_local_path):
            try:
                pil_img = Image.open(metadata.thumbnail_local_path).convert("RGB")
                self._apply_pil_image(pil_img, load_id)
                return
            except Exception as e:
                log_error(f"Erro ao abrir thumb local: {e}")

        # 2. URL de Thumbnail
        if metadata.thumbnail_url:
            self._load_thumbnail_async(load_id, metadata.thumbnail_url, metadata.video_stream_url)
        # 3. Extração de frame
        elif metadata.video_stream_url:
            self._extract_frame_async(load_id, metadata.video_stream_url)
        else:
            self._set_placeholder_thumb("Sem Capa")

    def _display_playlist_view(self, metadata: MediaMetadata, load_id: int):
        self.single_view.pack_forget()
        self.playlist_view.pack(fill="both", expand=True)

        self.lbl_pl_title.configure(text=f"📂 {metadata.title}")
        self.lbl_pl_meta.configure(text=f"👤 {metadata.uploader} • {metadata.playlist_count} vídeos disponíveis")

        self.playlist_current_page = 0
        self._render_current_playlist_page()
        self._update_playlist_selection_ui()

        # Carrega miniatura da playlist
        if metadata.thumbnail_url:
            self._load_playlist_thumb_async(load_id, metadata.thumbnail_url)
        else:
            self.pl_thumb_label.configure(text="📁 Playlist", image="")

    def _render_current_playlist_page(self):
        """Renderiza apenas os vídeos da página ativa (limite de 30 por página)."""
        if not self.current_metadata or not self.current_metadata.playlist_items:
            return

        items = self.current_metadata.playlist_items
        total_items = len(items)
        total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)

        # Garante página válida
        self.playlist_current_page = max(0, min(self.playlist_current_page, total_pages - 1))
        curr_page = self.playlist_current_page

        start_idx = curr_page * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, total_items)
        page_items = items[start_idx:end_idx]

        # Atualiza barra de paginação
        self.lbl_page_info.configure(
            text=f"Página {curr_page + 1} de {total_pages} (Vídeos {start_idx + 1} a {end_idx} de {total_items})"
        )
        self.btn_prev_page.configure(state="normal" if curr_page > 0 else "disabled")
        self.btn_next_page.configure(state="normal" if curr_page < (total_pages - 1) else "disabled")

        # Limpa widgets da lista atual
        for widget in self.pl_scroll_area.winfo_children():
            widget.destroy()

        # Renderiza os itens da página atual
        for item in page_items:
            row = ctk.CTkFrame(self.pl_scroll_area, fg_color="#18181B", corner_radius=Theme.CORNER_RADIUS_SM)
            row.pack(fill="x", pady=2, padx=4)

            # Duração no lado direito
            lbl_dur = ctk.CTkLabel(
                row,
                text=item.duration_str,
                font=Theme.FONT_SMALL,
                text_color=Theme.TEXT_MUTED
            )
            lbl_dur.pack(side="right", padx=(8, 12))

            # Checkbox com número e título
            cb_var = ctk.BooleanVar(value=item.is_selected)
            cb = ctk.CTkCheckBox(
                row,
                text=f"#{item.index:02d}  {item.title}",
                variable=cb_var,
                font=Theme.FONT_BODY,
                text_color=Theme.TEXT_MAIN,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=4,
                fg_color=Theme.PRIMARY,
                hover_color=Theme.PRIMARY_HOVER,
                command=lambda it=item, v=cb_var: self._on_playlist_item_toggled(it, v)
            )
            cb.pack(side="left", padx=8, pady=6, fill="x", expand=True)

    def _on_playlist_item_toggled(self, item: PlaylistItem, var: ctk.BooleanVar):
        item.is_selected = var.get()
        self._update_playlist_selection_ui()

    def _update_playlist_selection_ui(self):
        if not self.current_metadata or not self.current_metadata.playlist_items:
            return

        items = self.current_metadata.playlist_items
        total = len(items)
        selected = sum(1 for it in items if it.is_selected)

        self.lbl_pl_selected_count.configure(
            text=f"{selected} de {total} selecionados",
            text_color=Theme.TEXT_MAIN if selected > 0 else Theme.DANGER
        )

        if self.on_selection_changed:
            self.on_selection_changed(selected, total)

    def _select_all_playlist_items(self):
        if not self.current_metadata or not self.current_metadata.playlist_items:
            return
        for it in self.current_metadata.playlist_items:
            it.is_selected = True
        self._render_current_playlist_page()
        self._update_playlist_selection_ui()

    def _deselect_all_playlist_items(self):
        if not self.current_metadata or not self.current_metadata.playlist_items:
            return
        for it in self.current_metadata.playlist_items:
            it.is_selected = False
        self._render_current_playlist_page()
        self._update_playlist_selection_ui()

    def _prev_page(self):
        if self.playlist_current_page > 0:
            self.playlist_current_page -= 1
            self._render_current_playlist_page()

    def _next_page(self):
        if not self.current_metadata:
            return
        total_items = len(self.current_metadata.playlist_items)
        total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
        if self.playlist_current_page < total_pages - 1:
            self.playlist_current_page += 1
            self._render_current_playlist_page()

    def _load_playlist_thumb_async(self, load_id: int, thumb_url: str):
        def fetch():
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
                    'Accept': 'image/*,*/*;q=0.8',
                }
                req = urllib.request.Request(thumb_url, headers=headers)
                with urllib.request.urlopen(req, timeout=5, context=get_ssl_context()) as resp:
                    raw_data = resp.read()

                pil_img = Image.open(io.BytesIO(raw_data)).convert("RGB")
                pil_resized = pil_img.resize((140, 85), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=pil_resized, dark_image=pil_resized, size=(140, 85))

                def apply_ui():
                    if load_id == self._current_load_id:
                        self.playlist_thumb_image = ctk_img
                        self.pl_thumb_label.configure(image=ctk_img, text="")

                self._safe_ui_dispatch(apply_ui)
            except Exception:
                pass

        threading.Thread(target=fetch, daemon=True).start()

    def _load_thumbnail_async(self, load_id: int, thumb_url: str, video_stream_url: Optional[str] = None):
        self._set_placeholder_thumb("Carregando...")

        def fetch():
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                }
                req = urllib.request.Request(thumb_url, headers=headers)
                with urllib.request.urlopen(req, timeout=5, context=get_ssl_context()) as resp:
                    raw_data = resp.read()

                pil_img = Image.open(io.BytesIO(raw_data)).convert("RGB")
                self._safe_ui_dispatch(self._apply_pil_image, pil_img, load_id)

            except Exception as e:
                log_warning(f"Falha ao carregar thumb web: {e}")
                if load_id != self._current_load_id:
                    return
                if video_stream_url:
                    self._extract_frame_async(load_id, video_stream_url)
                else:
                    self._safe_ui_dispatch(self._set_placeholder_thumb, "Sem Prévia")

        threading.Thread(target=fetch, daemon=True).start()

    def _extract_frame_async(self, load_id: int, video_url: str):
        def worker():
            try:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                    temp_jpg = tf.name

                success = extract_frame_with_ffmpeg(video_url, temp_jpg)
                if load_id != self._current_load_id:
                    try:
                        os.remove(temp_jpg)
                    except Exception:
                        pass
                    return

                if success and os.path.exists(temp_jpg):
                    pil_img = Image.open(temp_jpg).convert("RGB")
                    self._safe_ui_dispatch(self._apply_pil_image, pil_img, load_id)
                    try:
                        os.remove(temp_jpg)
                    except Exception:
                        pass
                else:
                    self._safe_ui_dispatch(self._set_placeholder_thumb, "Sem Prévia")
            except Exception as e:
                log_error(f"Erro na extração de frame: {e}")
                if load_id == self._current_load_id:
                    self._safe_ui_dispatch(self._set_placeholder_thumb, "Sem Prévia")

        threading.Thread(target=worker, daemon=True).start()

    def _apply_pil_image(self, pil_img: Image.Image, load_id: int):
        """Executado SEMPRE na thread principal da interface."""
        if load_id != self._current_load_id:
            return

        try:
            pil_resized = pil_img.resize((230, 130), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_resized, dark_image=pil_resized, size=(230, 130))
            self.thumb_image = ctk_img

            self.thumb_label.destroy()
            self.thumb_label = ctk.CTkLabel(self.thumb_container, text="", image=ctk_img)
            self.thumb_label.pack(fill="both", expand=True)
            log_info(f"Thumb renderizada com sucesso (load_id: {load_id})")
        except Exception as e:
            log_error(f"Erro ao renderizar imagem: {e}")
            self._set_placeholder_thumb("Sem Prévia")

    def _set_placeholder_thumb(self, message: str):
        self.thumb_image = None
        self.thumb_label.destroy()
        self.thumb_label = ctk.CTkLabel(
            self.thumb_container,
            text=message,
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_DIM
        )
        self.thumb_label.pack(fill="both", expand=True)

    def _on_download_thumb_click(self):
        if not self.current_metadata:
            return

        from src.config import DEFAULT_DOWNLOAD_DIR
        import tkinter.filedialog as fd

        safe_name = sanitize_filename(self.current_metadata.title)
        is_image = self.current_metadata.media_type == "image"
        default_file = f"{safe_name}.jpg" if is_image else f"{safe_name}_thumb.jpg"

        dest = fd.asksaveasfilename(
            initialfile=default_file,
            initialdir=DEFAULT_DOWNLOAD_DIR,
            defaultextension=".jpg",
            filetypes=[("Imagem JPEG", "*.jpg"), ("Todos os Arquivos", "*.*")]
        )
        if dest:
            target_url = None
            if is_image and self.current_metadata.image_urls:
                target_url = self.current_metadata.image_urls[0]
            elif self.current_metadata.thumbnail_url:
                target_url = self.current_metadata.thumbnail_url

            if self.current_metadata.thumbnail_local_path and os.path.exists(self.current_metadata.thumbnail_local_path) and not is_image:
                import shutil
                shutil.copyfile(self.current_metadata.thumbnail_local_path, dest)
                if self.on_status_message:
                    self.on_status_message("Thumbnail salva com sucesso!", "success")
            elif target_url:
                ok = download_thumbnail_image(target_url, dest)
                if self.on_status_message:
                    if ok:
                        msg = "Foto salva com sucesso!" if is_image else "Thumbnail salva com sucesso!"
                        self.on_status_message(msg, "success")
                    else:
                        msg = "Falha ao salvar foto." if is_image else "Falha ao salvar thumbnail."
                        self.on_status_message(msg, "error")
