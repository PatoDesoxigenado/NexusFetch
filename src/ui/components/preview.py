"""Card de visualização de metadados da mídia com Queue Thread-Safe."""
import os
import io
import ssl
import urllib.request
import threading
import tempfile
from typing import Optional, Callable
from PIL import Image
import customtkinter as ctk
from src.ui.theme import Theme
from src.core.metadata import MediaMetadata, download_thumbnail_image, extract_frame_with_ffmpeg, get_ssl_context
from src.utils.helpers import sanitize_filename
from src.utils.logger import log_info, log_error, log_warning

class MediaPreviewCard(ctk.CTkFrame):
    def __init__(self, parent, on_status_message: Optional[Callable[[str, str], None]] = None, app_instance=None):
        super().__init__(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.on_status_message = on_status_message
        self.app_instance = app_instance
        self.current_metadata: Optional[MediaMetadata] = None
        self.thumb_image: Optional[ctk.CTkImage] = None
        self._current_load_id = 0

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

        # 1. Coluna Esquerda: Thumbnail
        self.thumb_container = ctk.CTkFrame(
            self.content_frame,
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

        # 2. Coluna Direita: Informações
        self.info_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.info_container.pack(side="left", fill="both", expand=True)

        # Título
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

        # Metadados secundários (Autor e Duração)
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

        # Linha inferior de ações
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

    def reset_to_empty(self):
        """Limpa completamente o card cancelando threads pendentes."""
        self._current_load_id += 1
        self.current_metadata = None
        self._set_placeholder_thumb("Aguardando link...")
        self.lbl_title.configure(text="Aguardando mídia para análise")
        self.lbl_uploader.configure(text="👤 --")
        self.lbl_duration.configure(text="⏱️ --:--")
        self.btn_download_thumb.configure(text="📥 Baixar Thumbnail HD", state="disabled")

    def display_metadata(self, metadata: MediaMetadata):
        """Atualiza o card com os dados da mídia."""
        self._current_load_id += 1
        load_id = self._current_load_id

        self.current_metadata = metadata
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

            # Recria o label garantindo widget limpo a cada nova imagem
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
