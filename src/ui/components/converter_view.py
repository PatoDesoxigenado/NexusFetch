"""Interface gráfica completa e intuitiva do Conversor de Mídia Integrado."""
import os
import sys
import threading
from typing import List, Optional, Callable
import customtkinter as ctk
from tkinter import filedialog

from src.ui.theme import Theme
from src.config import DEFAULT_DOWNLOAD_DIR
from src.core.converter import (
    MediaConverter,
    MediaFileInfo,
    probe_media_file,
    ALL_SUPPORTED_EXTS,
    SUPPORTED_VIDEO_EXTS,
    SUPPORTED_AUDIO_EXTS,
    TARGET_VIDEO_FORMATS,
    TARGET_AUDIO_FORMATS,
    RESOLUTION_PRESETS,
    MP4_CODECS,
)
from src.utils.logger import log_info, log_error

class ConverterView(ctk.CTkFrame):
    def __init__(self, parent, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.converter = MediaConverter()

        self.selected_files: List[MediaFileInfo] = []
        self.download_dir = DEFAULT_DOWNLOAD_DIR
        self.is_converting = False

        # Variáveis de Configuração
        self.var_target_format = ctk.StringVar(value="MP4")
        self.var_resolution = ctk.StringVar(value="Manter Resolução Original")
        self.var_codec = ctk.StringVar(value="H.264 / AVC (Padrão - Alta Compatibilidade)")

        self._build_ui()
        self._setup_drag_and_drop()

    def _build_ui(self):
        # 1. Card de Boas-Vindas & Explicação Exclusiva do Conversor
        self.info_card = ctk.CTkFrame(
            self,
            fg_color=Theme.CONVERTER_BG_LIGHT,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.CONVERTER_BORDER
        )
        self.info_card.pack(fill="x", pady=(0, 12))

        info_inner = ctk.CTkFrame(self.info_card, fg_color="transparent")
        info_inner.pack(fill="x", padx=20, pady=16)

        header_row = ctk.CTkFrame(info_inner, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            header_row,
            text="🔄",
            font=("Segoe UI", 20),
            text_color=Theme.CONVERTER_PRIMARY
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header_row,
            text="Conversor Multimídia Integrado (FFmpeg Nativo)",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN
        ).pack(side="left")

        ctk.CTkLabel(
            info_inner,
            text="Converta seus vídeos e áudios com alta performance, segurança atômica e máxima qualidade localmente na sua máquina, sem anúncios, sem riscos de vírus e sem compressão destrutiva de sites de terceiros.",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MUTED,
            wraplength=800,
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # Badges Explicativas dos Modos Suportados
        badges_container = ctk.CTkFrame(info_inner, fg_color="transparent")
        badges_container.pack(fill="x")

        self._create_info_badge(badges_container, "🎬 MP4 ➔ MP4 (Resoluções até 4K & Codecs H.264, HEVC, AV1, VP9)")
        self._create_info_badge(badges_container, "🎞️ Formatos Famosos (MKV, AVI, MOV, WEBM)")
        self._create_info_badge(badges_container, "🎵 Extração MP3 (320 kbps Máxima Fidelidade)")
        self._create_info_badge(badges_container, "🎧 Áudios (WAV, FLAC, M4A, OGG, OPUS)")
        self._create_info_badge(badges_container, "⚡ Múltiplos Arquivos em Lote")

        # 2. Área Interativa de Arrastar e Soltar (Drop Zone) & Seleção via Explorer
        self.drop_frame = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=2,
            border_color=Theme.BORDER
        )
        self.drop_frame.pack(fill="x", pady=(0, 12))

        # Evento de clique na drop zone inteira abre o seletor do explorer
        self.drop_frame.bind("<Button-1>", lambda e: self._open_file_dialog())

        drop_inner = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        drop_inner.pack(fill="x", padx=20, pady=24)
        drop_inner.bind("<Button-1>", lambda e: self._open_file_dialog())

        self.drop_icon = ctk.CTkLabel(
            drop_inner,
            text="📂",
            font=("Segoe UI", 36),
            text_color=Theme.CONVERTER_PRIMARY
        )
        self.drop_icon.pack(pady=(0, 6))
        self.drop_icon.bind("<Button-1>", lambda e: self._open_file_dialog())

        self.drop_title = ctk.CTkLabel(
            drop_inner,
            text="Arraste e solte seus arquivos de vídeo ou áudio aqui",
            font=Theme.FONT_TITLE,
            text_color=Theme.TEXT_MAIN
        )
        self.drop_title.pack(pady=(0, 4))
        self.drop_title.bind("<Button-1>", lambda e: self._open_file_dialog())

        self.drop_sub = ctk.CTkLabel(
            drop_inner,
            text="Ou clique nesta área para escolher arquivos pelo Explorador (suporta múltiplos arquivos simultâneos)",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_NORMAL
        )
        self.drop_sub.pack(pady=(0, 12))
        self.drop_sub.bind("<Button-1>", lambda e: self._open_file_dialog())

        self.btn_select_files = ctk.CTkButton(
            drop_inner,
            text="📁 Selecionar Arquivos no Computador",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.CONVERTER_PRIMARY,
            hover_color=Theme.CONVERTER_HOVER,
            text_color=Theme.TEXT_MAIN,
            height=40,
            width=270,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._open_file_dialog
        )
        self.btn_select_files.pack()

        # 3. Lista de Arquivos Selecionados (Oculta até adicionar arquivos)
        self.queue_frame = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )

        queue_header = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
        queue_header.pack(fill="x", padx=16, pady=(14, 8))

        self.lbl_queue_count = ctk.CTkLabel(
            queue_header,
            text="Arquivos Selecionados (0)",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN
        )
        self.lbl_queue_count.pack(side="left")

        self.btn_clear_all = ctk.CTkButton(
            queue_header,
            text="🗑️ Limpar Todos",
            font=Theme.FONT_SMALL,
            fg_color="transparent",
            hover_color=Theme.BG_DARK,
            text_color=Theme.DANGER,
            border_width=1,
            border_color=Theme.DANGER,
            height=28,
            width=110,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._clear_all_files
        )
        self.btn_clear_all.pack(side="right")

        self.btn_add_more = ctk.CTkButton(
            queue_header,
            text="➕ Adicionar Mais",
            font=Theme.FONT_SMALL,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_MAIN,
            height=28,
            width=130,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._open_file_dialog
        )
        self.btn_add_more.pack(side="right", padx=(0, 8))

        # Container interno rolável para itens da fila
        self.files_scroll = ctk.CTkScrollableFrame(
            self.queue_frame,
            fg_color="transparent",
            height=130
        )
        self.files_scroll.pack(fill="x", padx=14, pady=(0, 14))

        # 4. Painel de Opções de Conversão
        self.options_frame = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )

        opt_inner = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        opt_inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(
            opt_inner,
            text="⚙️ Configurações de Saída",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN
        ).pack(anchor="w", pady=(0, 10))

        # Linha de Seleção: Formato, Resolução e Codec
        selectors_row = ctk.CTkFrame(opt_inner, fg_color="transparent")
        selectors_row.pack(fill="x", pady=(0, 12))

        # Formato de Saída
        fmt_group = ctk.CTkFrame(selectors_row, fg_color="transparent")
        fmt_group.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(
            fmt_group,
            text="FORMATO DE DESTINO:",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_NORMAL
        ).pack(anchor="w", pady=(0, 4))

        self.menu_format = ctk.CTkOptionMenu(
            fmt_group,
            variable=self.var_target_format,
            values=TARGET_VIDEO_FORMATS + ["MP3 (Extrair Áudio 320k)"],
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_INPUT,
            button_color=Theme.SECONDARY,
            button_hover_color=Theme.SECONDARY_HOVER,
            dropdown_fg_color=Theme.BG_CARD_LIGHT,
            dropdown_hover_color=Theme.CONVERTER_PRIMARY,
            text_color=Theme.TEXT_MAIN,
            dropdown_text_color=Theme.TEXT_MAIN,
            height=34,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_format_changed
        )
        self.menu_format.pack(fill="x")

        # Resolução de Saída
        self.res_group = ctk.CTkFrame(selectors_row, fg_color="transparent")
        self.res_group.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_res = ctk.CTkLabel(
            self.res_group,
            text="RESOLUÇÃO DE VÍDEO:",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_NORMAL
        )
        self.lbl_res.pack(anchor="w", pady=(0, 4))

        res_labels = [label for _, label in RESOLUTION_PRESETS]
        self.menu_resolution = ctk.CTkOptionMenu(
            self.res_group,
            variable=self.var_resolution,
            values=res_labels,
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_INPUT,
            button_color=Theme.SECONDARY,
            button_hover_color=Theme.SECONDARY_HOVER,
            dropdown_fg_color=Theme.BG_CARD_LIGHT,
            dropdown_hover_color=Theme.CONVERTER_PRIMARY,
            text_color=Theme.TEXT_MAIN,
            dropdown_text_color=Theme.TEXT_MAIN,
            height=34,
            corner_radius=Theme.CORNER_RADIUS_SM
        )
        self.menu_resolution.pack(fill="x")

        # Codec de Vídeo (Exclusivo para MP4 -> MP4)
        self.codec_group = ctk.CTkFrame(selectors_row, fg_color="transparent")
        self.codec_group.pack(side="left", fill="x", expand=True)

        self.lbl_codec = ctk.CTkLabel(
            self.codec_group,
            text="CODEC (LIBERADO EM MP4 ➔ MP4):",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_NORMAL
        )
        self.lbl_codec.pack(anchor="w", pady=(0, 4))

        codec_labels = [label for _, label in MP4_CODECS]
        self.menu_codec = ctk.CTkOptionMenu(
            self.codec_group,
            variable=self.var_codec,
            values=codec_labels,
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_INPUT,
            button_color=Theme.SECONDARY,
            button_hover_color=Theme.SECONDARY_HOVER,
            dropdown_fg_color=Theme.BG_CARD_LIGHT,
            dropdown_hover_color=Theme.CONVERTER_PRIMARY,
            text_color=Theme.TEXT_MAIN,
            dropdown_text_color=Theme.TEXT_MAIN,
            height=34,
            corner_radius=Theme.CORNER_RADIUS_SM
        )
        self.menu_codec.pack(fill="x")

        # Linha da Pasta de Destino
        dest_row = ctk.CTkFrame(opt_inner, fg_color="transparent")
        dest_row.pack(fill="x", pady=(4, 0))

        self.lbl_dest_path = ctk.CTkLabel(
            dest_row,
            text=f"SALVAR EM: {self.download_dir}",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_NORMAL,
            anchor="w"
        )
        self.lbl_dest_path.pack(side="left", fill="x", expand=True)

        btn_change_dir = ctk.CTkButton(
            dest_row,
            text="📁 Alterar Pasta",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_NORMAL,
            border_width=1,
            border_color=Theme.BORDER_SUBTLE,
            height=28,
            width=115,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._change_output_directory
        )
        btn_change_dir.pack(side="right")

        # 5. Barra de Ação & Progresso da Conversão
        self.action_frame = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.action_frame.pack(fill="x", pady=(12, 0))

        act_inner = ctk.CTkFrame(self.action_frame, fg_color="transparent")
        act_inner.pack(fill="x", padx=20, pady=16)

        # Informações de Status e Telemetria
        self.status_row = ctk.CTkFrame(act_inner, fg_color="transparent")
        self.status_row.pack(fill="x", pady=(0, 6))

        self.lbl_status = ctk.CTkLabel(
            self.status_row,
            text="Pronto para converter",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MAIN
        )
        self.lbl_status.pack(side="left")

        self.lbl_metrics = ctk.CTkLabel(
            self.status_row,
            text="",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_NORMAL
        )
        self.lbl_metrics.pack(side="right")

        # Barra de Progresso
        self.progress_bar = ctk.CTkProgressBar(
            act_inner,
            fg_color=Theme.BG_INPUT,
            progress_color=Theme.CONVERTER_PRIMARY,
            height=10,
            corner_radius=Theme.CORNER_RADIUS_SM
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(0, 12))

        # Botões de Ação
        btn_row = ctk.CTkFrame(act_inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_convert = ctk.CTkButton(
            btn_row,
            text="⚡ CONVERTER ARQUIVOS",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.CONVERTER_PRIMARY,
            hover_color=Theme.CONVERTER_HOVER,
            text_color=Theme.TEXT_MAIN,
            height=44,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._start_conversion
        )
        self.btn_convert.pack(side="left", fill="x", expand=True)

        self.btn_cancel = ctk.CTkButton(
            btn_row,
            text="⛔ Cancelar (Esc)",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.DANGER,
            text_color=Theme.TEXT_MAIN,
            border_width=1,
            border_color=Theme.BORDER,
            height=44,
            width=140,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._cancel_conversion
        )

        self.btn_open_folder = ctk.CTkButton(
            btn_row,
            text="📂 Abrir Pasta",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            text_color="#FFFFFF",
            height=44,
            width=150,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._open_output_folder
        )

        self._refresh_codec_state()

    def _create_info_badge(self, parent, text: str):
        badge = ctk.CTkFrame(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CONVERTER_BORDER
        )
        badge.pack(side="left", padx=(0, 8), pady=2)
        ctk.CTkLabel(
            badge,
            text=text,
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.CONVERTER_TEXT_BRIGHT
        ).pack(padx=10, pady=4)

    def _setup_drag_and_drop(self):
        """Conecta o arrastar e soltar (Drag and Drop) no Windows se disponível."""
        if sys.platform == "win32":
            try:
                import windnd
                def on_drop(files):
                    # Só processa se a aba ativa for o Conversor
                    if getattr(self.app, "active_module", "") != "converter":
                        return

                    file_paths = []
                    for f in files:
                        if isinstance(f, bytes):
                            try:
                                decoded = f.decode("utf-8")
                            except UnicodeDecodeError:
                                decoded = f.decode("mbcs", errors="replace")
                            file_paths.append(decoded)
                        else:
                            file_paths.append(str(f))

                    self.app.run_on_ui(self._add_files_from_paths, file_paths)

                # Hook na janela principal com force_unicode=True para suporte a caracteres especiais
                windnd.hook_dropfiles(self.app, func=on_drop, force_unicode=True)
            except Exception as e:
                log_info(f"Drag and drop windnd não conectado: {e}")

    def _open_file_dialog(self):
        """Abre o diálogo nativo do sistema operacional para seleção múltipla de arquivos."""
        file_types = [
            ("Arquivos de Mídia (Vídeo e Áudio)", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.ts *.wmv *.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus"),
            ("Vídeos (*.mp4, *.mkv, *.avi, *.mov, *.webm)", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.ts *.wmv"),
            ("Áudios (*.mp3, *.wav, *.flac, *.m4a, *.ogg)", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus"),
            ("Todos os Arquivos", "*.*")
        ]
        paths = filedialog.askopenfilenames(
            title="Selecione um ou múltiplos arquivos para conversão",
            filetypes=file_types
        )
        if paths:
            self._add_files_from_paths(list(paths))

    def _add_files_from_paths(self, paths: List[str]):
        """Analisa os caminhos recebidos e adiciona à fila de arquivos."""
        existing_paths = {f.path for f in self.selected_files}
        new_items = []

        for p in paths:
            p = os.path.normpath(p)
            if not os.path.isfile(p):
                continue
            if p in existing_paths:
                continue

            ext = os.path.splitext(p)[1].lower()
            if ext not in ALL_SUPPORTED_EXTS:
                continue

            info = probe_media_file(p)
            if info:
                new_items.append(info)
                existing_paths.add(p)

        if new_items:
            self.selected_files.extend(new_items)
            self._update_queue_ui()
            self._adjust_options_for_files()

    def _update_queue_ui(self):
        """Atualiza a lista visual de arquivos selecionados."""
        count = len(self.selected_files)
        if count > 0:
            if not self.queue_frame.winfo_ismapped():
                self.queue_frame.pack(fill="x", pady=(0, 12), before=self.action_frame)
            if not self.options_frame.winfo_ismapped():
                self.options_frame.pack(fill="x", pady=(0, 12), before=self.action_frame)
            self.lbl_queue_count.configure(text=f"Arquivos na Fila ({count})")
            self.btn_convert.configure(text=f"⚡ CONVERTER {count} ARQUIVO{'S' if count > 1 else ''}")
        else:
            if self.queue_frame.winfo_ismapped():
                self.queue_frame.pack_forget()
            if self.options_frame.winfo_ismapped():
                self.options_frame.pack_forget()
            self.btn_convert.configure(text="⚡ CONVERTER ARQUIVOS")

        # Limpa widgets antigos
        for child in self.files_scroll.winfo_children():
            child.destroy()

        # Cria linha para cada arquivo
        for f in self.selected_files:
            row = ctk.CTkFrame(
                self.files_scroll,
                fg_color=Theme.BG_CARD_LIGHT,
                corner_radius=Theme.CORNER_RADIUS_SM,
                border_width=1,
                border_color=Theme.BORDER_SUBTLE
            )
            row.pack(fill="x", pady=2)

            icon_str = "🎥" if f.is_video else "🎵"
            ctk.CTkLabel(row, text=icon_str, font=("Segoe UI", 16)).pack(side="left", padx=(10, 6))

            # Nome e detalhes
            name_text = f.name if len(f.name) <= 45 else f"{f.name[:42]}..."
            details_text = f"{f.size_str} • {f.duration_str}"
            if f.is_video and f.width and f.height:
                details_text += f" • {f.resolution_str}"

            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="x", expand=True, padx=4, pady=4)

            ctk.CTkLabel(text_frame, text=name_text, font=Theme.FONT_BODY_BOLD, text_color=Theme.TEXT_MAIN, anchor="w").pack(fill="x")
            ctk.CTkLabel(text_frame, text=details_text, font=Theme.FONT_SMALL, text_color=Theme.TEXT_NORMAL, anchor="w").pack(fill="x")

            # Formato original tag
            ctk.CTkLabel(row, text=f.ext.upper(), font=Theme.FONT_BADGE, text_color=Theme.CONVERTER_TEXT_BRIGHT).pack(side="left", padx=8)

            # Botão remover
            btn_remove = ctk.CTkButton(
                row,
                text="✖",
                font=("Segoe UI", 11, "bold"),
                width=24,
                height=24,
                fg_color="transparent",
                hover_color=Theme.DANGER,
                text_color=Theme.TEXT_NORMAL,
                command=lambda p=f.path: self._remove_file(p)
            )
            btn_remove.pack(side="right", padx=(0, 8))

    def _remove_file(self, path: str):
        self.selected_files = [f for f in self.selected_files if f.path != path]
        self._update_queue_ui()
        self._adjust_options_for_files()

    def _clear_all_files(self):
        self.selected_files.clear()
        self._update_queue_ui()
        self._adjust_options_for_files()

    def _adjust_options_for_files(self):
        """Ajusta as opções disponíveis dependendo se os arquivos são vídeos ou áudios."""
        if not self.selected_files:
            return

        has_videos = any(f.is_video for f in self.selected_files)
        has_audios = any(f.is_audio for f in self.selected_files)

        # Se só temos áudios, restringe formatos de saída para áudios
        if has_audios and not has_videos:
            self.menu_format.configure(values=TARGET_AUDIO_FORMATS)
            if self.var_target_format.get() not in TARGET_AUDIO_FORMATS:
                self.var_target_format.set("MP3")
        else:
            self.menu_format.configure(values=TARGET_VIDEO_FORMATS + ["MP3 (Extrair Áudio 320k)"])
            if self.var_target_format.get() not in (TARGET_VIDEO_FORMATS + ["MP3 (Extrair Áudio 320k)"]):
                self.var_target_format.set("MP4")

        self._on_format_changed(self.var_target_format.get())

    def _on_format_changed(self, selected_fmt: str):
        """Gerencia visibilidade dinâmica de resolução e codec conforme solicitação do usuário."""
        fmt_clean = selected_fmt.lower().replace(" (extrair áudio 320k)", "").replace(" (extrair áudio)", "").strip()
        is_audio = fmt_clean in {"mp3", "wav", "flac", "m4a", "ogg", "opus"}

        if is_audio:
            # Ao selecionar áudio (MP3, WAV, etc.), a resolução e o codec SUMEM da tela
            if self.res_group.winfo_ismapped():
                self.res_group.pack_forget()
            if self.codec_group.winfo_ismapped():
                self.codec_group.pack_forget()
        else:
            # Para formatos de vídeo, exibe a opção de resolução
            if not self.res_group.winfo_ismapped():
                self.res_group.pack(side="left", fill="x", expand=True, padx=(0, 10))

            # A seleção de CODECs SÓ é visível se a entrada for MP4 e a saída for MP4
            all_mp4_input = bool(self.selected_files) and all(f.ext == ".mp4" for f in self.selected_files)
            is_mp4_target = (fmt_clean == "mp4")

            if all_mp4_input and is_mp4_target:
                if not self.codec_group.winfo_ismapped():
                    self.codec_group.pack(side="left", fill="x", expand=True)
                self.menu_codec.configure(state="normal")
                self.lbl_codec.configure(text="CODEC (LIBERADO EM MP4 ➔ MP4):", text_color=Theme.CONVERTER_PRIMARY)
            else:
                # Nos outros formatos de vídeo (MKV, AVI, MOV, WEBM) ou entrada não MP4, SOME o codec
                if self.codec_group.winfo_ismapped():
                    self.codec_group.pack_forget()

    def _refresh_codec_state(self):
        """Atualiza a visibilidade condicional baseada na seleção atual."""
        self._on_format_changed(self.var_target_format.get())

    def _change_output_directory(self):
        folder = filedialog.askdirectory(initialdir=self.download_dir, title="Selecione a pasta de saída para os arquivos convertidos")
        if folder:
            self.download_dir = os.path.normpath(folder)
            self.lbl_dest_path.configure(text=f"SALVAR EM: {self.download_dir}")

    def _open_output_folder(self):
        """Abre a pasta de destino no explorador nativo."""
        try:
            if sys.platform == "win32":
                os.startfile(self.download_dir)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", self.download_dir])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", self.download_dir])
        except Exception as e:
            log_error(f"Erro ao abrir pasta: {e}")

    def _start_conversion(self):
        """Inicia a conversão dos arquivos selecionados em thread separada."""
        if not self.selected_files:
            self._open_file_dialog()
            return

        self.is_converting = True
        self.btn_convert.pack_forget()
        self.btn_open_folder.pack_forget()
        self.btn_cancel.pack(side="left", fill="x", expand=True)

        self.btn_select_files.configure(state="disabled")
        self.btn_add_more.configure(state="disabled")
        self.btn_clear_all.configure(state="disabled")
        self.menu_format.configure(state="disabled")
        self.menu_resolution.configure(state="disabled")
        self.menu_codec.configure(state="disabled")

        self.progress_bar.set(0.0)
        self.lbl_status.configure(text="Iniciando conversão acelerada...", text_color=Theme.CONVERTER_TEXT_BRIGHT)
        self.lbl_metrics.configure(text="", text_color=Theme.TEXT_NORMAL)

        # Mapeia resolução selecionada
        res_label = self.var_resolution.get()
        res_key = "original"
        for k, l in RESOLUTION_PRESETS:
            if l == res_label:
                res_key = k
                break

        # Mapeia codec selecionado
        codec_label = self.var_codec.get()
        codec_key = "h264"
        for k, l in MP4_CODECS:
            if l == codec_label:
                codec_key = k
                break

        target_fmt = self.var_target_format.get()
        output_dir = self.download_dir
        files_to_convert = list(self.selected_files)

        def worker():
            def on_progress(file_idx, total_files, file_pct, total_pct, speed_str, status_msg):
                def update_ui():
                    self.progress_bar.set(total_pct / 100.0)
                    self.lbl_status.configure(
                        text=f"[{file_idx}/{total_files}] {status_msg}",
                        text_color=Theme.CONVERTER_TEXT_BRIGHT
                    )
                    metrics_str = f"Velocidade: {speed_str} • Geral: {total_pct:.1f}%"
                    self.lbl_metrics.configure(text=metrics_str, text_color=Theme.TEXT_NORMAL)
                self.app.run_on_ui(update_ui)

            success, total, errors = self.converter.convert_batch(
                files=files_to_convert,
                output_dir=output_dir,
                target_format=target_fmt,
                resolution_key=res_key,
                codec_key=codec_key,
                on_progress=on_progress
            )

            def on_finish():
                self.is_converting = False
                self.btn_cancel.pack_forget()
                self.btn_convert.pack(side="left", fill="x", expand=True)
                self.btn_open_folder.pack(side="right", padx=(10, 0))

                self.btn_select_files.configure(state="normal")
                self.btn_add_more.configure(state="normal")
                self.btn_clear_all.configure(state="normal")
                self.menu_format.configure(state="normal")
                self.menu_resolution.configure(state="normal")
                self._refresh_codec_state()

                if success == total and total > 0:
                    self.progress_bar.set(1.0)
                    self.lbl_status.configure(
                        text=f"✅ Todos os {total} arquivo(s) foram convertidos com sucesso!",
                        text_color=Theme.SUCCESS
                    )
                    self.lbl_metrics.configure(text="Concluído 100%")
                elif success > 0:
                    self.lbl_status.configure(
                        text=f"⚠️ {success} de {total} arquivo(s) convertidos. Alguns falharam.",
                        text_color=Theme.WARNING
                    )
                else:
                    self.lbl_status.configure(
                        text="❌ Nenhum arquivo pôde ser convertido.",
                        text_color=Theme.DANGER
                    )

            self.app.run_on_ui(on_finish)

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_conversion(self):
        """Cancela a conversão atual."""
        self.converter.cancel()
        self.lbl_status.configure(text="Cancelando conversão...", text_color=Theme.WARNING)
