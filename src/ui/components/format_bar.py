"""Barra inteligente de formato, qualidade com estimativa de tamanho e diretório."""
import os
import tkinter.filedialog as fd
from typing import List, Optional, Callable
import customtkinter as ctk
from src.ui.theme import Theme
from src.config import DEFAULT_DOWNLOAD_DIR
from src.core.metadata import VideoQualityOption, MediaMetadata
from src.utils.helpers import format_bytes

class FormatSelectionBar(ctk.CTkFrame):
    def __init__(self, parent, on_options_changed: Optional[Callable[[], None]] = None):
        super().__init__(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.on_options_changed = on_options_changed
        self.download_dir = DEFAULT_DOWNLOAD_DIR
        self.video_qualities: List[VideoQualityOption] = []
        self.current_mode = "video"  # "video", "audio", "image", "gif"
        self.media_type = "video"
        self.estimated_audio_bytes = 0

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=16, pady=14)

        # 1. Linha Superior: Formato e Qualidade
        top_row = ctk.CTkFrame(container, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 12))

        # Seletor de Formato
        self.format_group = ctk.CTkFrame(top_row, fg_color="transparent")
        self.format_group.pack(side="left", padx=(0, 20))

        self.lbl_format = ctk.CTkLabel(
            self.format_group,
            text="FORMATO:",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_format.pack(anchor="w", pady=(0, 4))

        self.seg_format = ctk.CTkSegmentedButton(
            self.format_group,
            values=["🎬 Vídeo (MP4)", "🎵 Áudio (MP3)"],
            font=Theme.FONT_BODY_BOLD,
            fg_color=Theme.BG_DARK,
            selected_color=Theme.PRIMARY,
            selected_hover_color=Theme.PRIMARY_HOVER,
            unselected_color=Theme.BG_DARK,
            unselected_hover_color=Theme.SECONDARY_HOVER,
            corner_radius=Theme.CORNER_RADIUS_SM,
            height=34,
            command=self._on_format_changed
        )
        self.seg_format.set("🎬 Vídeo (MP4)")
        self.seg_format.pack()

        # Seletor de Qualidade / Resolução
        self.quality_group = ctk.CTkFrame(top_row, fg_color="transparent")
        self.quality_group.pack(side="left", fill="x", expand=True)

        self.lbl_quality = ctk.CTkLabel(
            self.quality_group,
            text="QUALIDADE & TAMANHO ESTIMADO:",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_quality.pack(anchor="w", pady=(0, 4))

        self.opt_quality = ctk.CTkOptionMenu(
            self.quality_group,
            values=["🌟 Máxima Resolução (Padrão)"],
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_DARK,
            button_color=Theme.SECONDARY,
            button_hover_color=Theme.SECONDARY_HOVER,
            dropdown_fg_color=Theme.BG_CARD_LIGHT,
            dropdown_hover_color=Theme.PRIMARY,
            dropdown_text_color=Theme.TEXT_MAIN,
            corner_radius=Theme.CORNER_RADIUS_SM,
            height=34,
            command=lambda val: self._notify_change()
        )
        self.opt_quality.pack(fill="x")

        # 2. Linha Inferior: Diretório de Destino
        dir_row = ctk.CTkFrame(container, fg_color="transparent")
        dir_row.pack(fill="x")

        lbl_dir_title = ctk.CTkLabel(
            dir_row,
            text="SALVAR EM:",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_MUTED
        )
        lbl_dir_title.pack(side="left", padx=(0, 10))

        self.lbl_path = ctk.CTkLabel(
            dir_row,
            text=self.download_dir,
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MAIN,
            anchor="w"
        )
        self.lbl_path.pack(side="left", fill="x", expand=True, padx=(0, 10))

        btn_browse = ctk.CTkButton(
            dir_row,
            text="📁 Alterar Pasta",
            font=Theme.FONT_SMALL,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            width=110,
            height=26,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_choose_folder
        )
        btn_browse.pack(side="right")

    def configure_for_media(self, metadata: MediaMetadata):
        """Ajusta os botões e opções dinamicamente para o tipo de mídia (Vídeo, Áudio, Imagem ou GIF)."""
        self.media_type = metadata.media_type
        self.video_qualities = metadata.qualities
        self.estimated_audio_bytes = metadata.estimated_audio_size or 0

        if self.media_type == "image":
            # Caso seja imagem (Twitter photo)
            self.current_mode = "image"
            self.seg_format.configure(values=["🖼️ Imagem (Foto)"])
            self.seg_format.set("🖼️ Imagem (Foto)")
            labels = [q.label for q in metadata.qualities] or ["🖼️ Imagem Original"]
            self.opt_quality.configure(values=labels)
            self.opt_quality.set(labels[0])
            self.opt_quality.configure(state="normal")

        elif self.media_type == "gif":
            # Caso seja GIF (Twitter gif animado)
            self.current_mode = "gif"
            self.seg_format.configure(values=["🎞️ Animação (.GIF)", "🎬 Vídeo (.MP4)"])
            self.seg_format.set("🎞️ Animação (.GIF)")
            self.opt_quality.configure(values=["🎞️ Animação GIF (Paleta 256 cores)"])
            self.opt_quality.set("🎞️ Animação GIF (Paleta 256 cores)")
            self.opt_quality.configure(state="disabled")

        else:
            # Caso padrão: Vídeo com faixa de áudio
            self.current_mode = "video"
            self.seg_format.configure(values=["🎬 Vídeo (MP4)", "🎵 Áudio (MP3)"])
            self.seg_format.set("🎬 Vídeo (MP4)")
            labels = [q.label for q in metadata.qualities] or ["🌟 Máxima Resolução"]
            self.opt_quality.configure(values=labels)
            self.opt_quality.set(labels[0])
            self.opt_quality.configure(state="normal")

        self._notify_change()

    def _on_format_changed(self, value: str):
        if "Áudio" in value:
            self.current_mode = "audio"
            audio_tag = f" ~ {format_bytes(self.estimated_audio_bytes)}" if self.estimated_audio_bytes > 0 else ""
            audio_label = f"🎵 MP3 - 320 kbps (Qualidade Máxima){audio_tag}"
            self.opt_quality.configure(values=[audio_label])
            self.opt_quality.set(audio_label)
            self.opt_quality.configure(state="disabled")

        elif "GIF" in value:
            self.current_mode = "gif"
            self.opt_quality.configure(values=["🎞️ Animação GIF (Paleta 256 cores)"])
            self.opt_quality.set("🎞️ Animação GIF (Paleta 256 cores)")
            self.opt_quality.configure(state="disabled")

        elif "Imagem" in value:
            self.current_mode = "image"
            labels = [q.label for q in self.video_qualities] or ["🖼️ Imagem Original"]
            self.opt_quality.configure(values=labels)
            self.opt_quality.set(labels[0])
            self.opt_quality.configure(state="normal")

        else:
            self.current_mode = "video"
            labels = [q.label for q in self.video_qualities] or ["🌟 Máxima Resolução"]
            self.opt_quality.configure(values=labels)
            self.opt_quality.set(labels[0])
            self.opt_quality.configure(state="normal")

        self._notify_change()

    def _on_choose_folder(self):
        chosen = fd.askdirectory(initialdir=self.download_dir, title="Selecione a Pasta de Destino")
        if chosen:
            self.download_dir = chosen
            self.lbl_path.configure(text=chosen)
            self._notify_change()

    def get_selected_options(self) -> tuple[str, Optional[str], str]:
        """Retorna (mode, format_id, output_dir)."""
        mode = self.current_mode
        format_id = None

        if mode == "image":
            format_id = "photo_orig"
        elif mode == "gif":
            format_id = "gif_convert"
        elif mode == "video" and self.video_qualities:
            selected_label = self.opt_quality.get()
            for q in self.video_qualities:
                if q.label == selected_label:
                    format_id = q.format_id
                    break

        return mode, format_id, self.download_dir

    def _notify_change(self):
        if self.on_options_changed:
            self.on_options_changed()
