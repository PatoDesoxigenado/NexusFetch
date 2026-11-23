"""Interface gráfica da aba de Recorte Rápido (Trim / Clip) para links remotos e arquivos locais."""
import os
import sys
import subprocess
import threading
from typing import List, Optional
import customtkinter as ctk
from tkinter import filedialog

from src.core.trimmer import (
    MediaTrimmer,
    TrimSourceInfo,
    TRIM_MODE_FAST,
    TRIM_MODE_PRECISE,
    REMOTE_QUALITY_OPTIONS,
    analyze_trim_source,
    parse_timestamp,
    format_timestamp_hms,
    validate_trim_range,
)
from src.core.converter import ALL_SUPPORTED_EXTS
from src.ui.theme import Theme
from src.utils.settings import get_setting, update_setting
from src.utils.notifications import notify_async


class TrimmerView(ctk.CTkFrame):
    """Aba de Recorte Rápido (Trim / Clip) acessível pelo menu Mais Opções (☰)."""

    def __init__(self, parent, app_instance=None):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.trimmer = MediaTrimmer()
        self.source_info: Optional[TrimSourceInfo] = None
        self.is_analyzing = False
        self.is_trimming = False
        self.output_dir = get_setting("download_dir")

        self.var_output_type = ctk.StringVar(value="Vídeo (MP4)")
        self.var_quality = ctk.StringVar(value=REMOTE_QUALITY_OPTIONS[0][0])

        self._build_ui()

    def _safe_ui(self, fn, *args, **kwargs):
        try:
            if self.app and hasattr(self.app, "run_on_ui"):
                self.app.run_on_ui(lambda: fn(*args, **kwargs))
            else:
                self.after(0, lambda: fn(*args, **kwargs))
        except Exception:
            pass

    def _build_ui(self):
        # 1. Card de Cabeçalho
        info_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color="#D97706",
        )
        info_card.pack(fill="x", pady=(0, 12))

        info_inner = ctk.CTkFrame(info_card, fg_color="transparent")
        info_inner.pack(fill="x", padx=20, pady=14)

        ctk.CTkLabel(
            info_inner,
            text="✂️  Recorte Rápido (Trim / Clip)",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN,
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            info_inner,
            text=(
                "Recorte apenas o trecho desejado de links (YouTube, Twitter/X, Instagram) sem baixar o vídeo completo, "
                "ou corte arquivos locais instantaneamente arrastando-os para esta tela."
            ),
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_NORMAL,
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

        # 2. Card da Fonte (Link ou Arquivo Local)
        source_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        source_card.pack(fill="x", pady=(0, 12))

        src_inner = ctk.CTkFrame(source_card, fg_color="transparent")
        src_inner.pack(fill="x", padx=18, pady=14)

        top_lbl = ctk.CTkFrame(src_inner, fg_color="transparent")
        top_lbl.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            top_lbl,
            text="FONTE (LINK OU ARQUIVO LOCAL):",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MUTED,
        ).pack(side="left")

        ctk.CTkButton(
            top_lbl,
            text="📂 Escolher Arquivo Local",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.BG_CARD_LIGHT,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_MAIN,
            height=28,
            width=165,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._select_local_file,
        ).pack(side="right")

        input_row = ctk.CTkFrame(src_inner, fg_color="transparent")
        input_row.pack(fill="x", pady=(0, 8))

        self.entry_source = ctk.CTkEntry(
            input_row,
            placeholder_text="Cole o link do YouTube/X/Instagram ou arraste um vídeo/áudio do PC...",
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BORDER_SUBTLE,
            text_color=Theme.TEXT_MAIN,
            height=38,
            corner_radius=Theme.CORNER_RADIUS_SM,
        )
        self.entry_source.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_source.bind("<Return>", lambda e: self._start_analysis())

        self.btn_paste = ctk.CTkButton(
            input_row,
            text="📋 Colar",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.BG_CARD_LIGHT,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_MAIN,
            width=82,
            height=38,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._paste_source,
        )
        self.btn_paste.pack(side="left", padx=(0, 6))

        self.btn_analyze = ctk.CTkButton(
            input_row,
            text="🔍 Analisar",
            font=Theme.FONT_BUTTON,
            fg_color="#D97706",
            hover_color="#B45309",
            text_color="#FFFFFF",
            width=125,
            height=38,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._start_analysis,
        )
        self.btn_analyze.pack(side="left")

        self.lbl_source_info = ctk.CTkLabel(
            src_inner,
            text="Cole um link e clique em 'Analisar' (ou escolha/arraste um arquivo local).",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MUTED,
            anchor="w",
        )
        self.lbl_source_info.pack(fill="x")

        # 3. Card de Intervalo de Tempo & Configurações
        cfg_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        cfg_card.pack(fill="x", pady=(0, 12))

        cfg_inner = ctk.CTkFrame(cfg_card, fg_color="transparent")
        cfg_inner.pack(fill="x", padx=18, pady=14)

        # Linha de Tempos (Início / Fim / Duração do Clipe)
        time_row = ctk.CTkFrame(cfg_inner, fg_color="transparent")
        time_row.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            time_row,
            text="INÍCIO:",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))

        self.entry_start = ctk.CTkEntry(
            time_row,
            width=115,
            height=34,
            font=Theme.FONT_BODY_BOLD,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BORDER_SUBTLE,
            text_color=Theme.TEXT_MAIN,
            justify="center",
        )
        self.entry_start.insert(0, "00:00:00")
        self.entry_start.pack(side="left", padx=(0, 16))
        self.entry_start.bind("<KeyRelease>", lambda e: self._update_clip_preview_label())

        ctk.CTkLabel(
            time_row,
            text="FIM:",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))

        self.entry_end = ctk.CTkEntry(
            time_row,
            width=115,
            height=34,
            font=Theme.FONT_BODY_BOLD,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BORDER_SUBTLE,
            text_color=Theme.TEXT_MAIN,
            justify="center",
        )
        self.entry_end.insert(0, "00:01:00")
        self.entry_end.pack(side="left", padx=(0, 16))
        self.entry_end.bind("<KeyRelease>", lambda e: self._update_clip_preview_label())

        self.lbl_clip_duration = ctk.CTkLabel(
            time_row,
            text="⏱️ Trecho: 00:01:00",
            font=Theme.FONT_BODY_BOLD,
            text_color="#D97706",
        )
        self.lbl_clip_duration.pack(side="left")

        # Linha de Opções (Formato, Modo, Qualidade)
        opt_row = ctk.CTkFrame(cfg_inner, fg_color="transparent")
        opt_row.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            opt_row,
            text="SAÍDA:",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))

        self.seg_output = ctk.CTkSegmentedButton(
            opt_row,
            values=["Vídeo (MP4)", "Áudio (MP3)"],
            variable=self.var_output_type,
            font=Theme.FONT_SMALL_BOLD,
            selected_color="#D97706",
            selected_hover_color="#B45309",
            height=32,
            command=self._on_output_type_changed,
        )
        self.seg_output.pack(side="left", padx=(0, 18))

        self.lbl_quality = ctk.CTkLabel(
            opt_row,
            text="QUALIDADE:",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MUTED,
        )
        self.lbl_quality.pack(side="left", padx=(0, 6))

        self.opt_quality = ctk.CTkOptionMenu(
            opt_row,
            values=[q[0] for q in REMOTE_QUALITY_OPTIONS],
            variable=self.var_quality,
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.BG_INPUT,
            button_color=Theme.BG_CARD_LIGHT,
            button_hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_MAIN,
            height=32,
            width=185,
        )
        self.opt_quality.pack(side="left")

        # Linha de Pasta de Destino
        folder_row = ctk.CTkFrame(cfg_inner, fg_color="transparent")
        folder_row.pack(fill="x")

        ctk.CTkLabel(
            folder_row,
            text="SALVAR EM:",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 8))

        self.lbl_folder = ctk.CTkLabel(
            folder_row,
            text=self.output_dir,
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MAIN,
        )
        self.lbl_folder.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            folder_row,
            text="📂 Alterar Pasta",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.BG_CARD_LIGHT,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_MAIN,
            height=30,
            width=125,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._change_folder,
        ).pack(side="right")

        # 4. Card de Ação & Progresso
        act_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        act_card.pack(fill="x")

        act_inner = ctk.CTkFrame(act_card, fg_color="transparent")
        act_inner.pack(fill="x", padx=18, pady=14)

        self.lbl_status = ctk.CTkLabel(
            act_inner,
            text="Analise um link ou selecione um arquivo local para liberar o recorte.",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MAIN,
            anchor="w",
        )
        self.lbl_status.pack(fill="x", pady=(0, 6))

        self.progress_bar = ctk.CTkProgressBar(
            act_inner,
            fg_color=Theme.BG_INPUT,
            progress_color="#D97706",
            height=10,
            corner_radius=Theme.CORNER_RADIUS_SM,
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(0, 12))

        btn_row = ctk.CTkFrame(act_inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_open_folder = ctk.CTkButton(
            btn_row,
            text="📂 Abrir Pasta",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            text_color="#FFFFFF",
            height=42,
            width=145,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._open_output_folder,
        )

        self.btn_cancel = ctk.CTkButton(
            btn_row,
            text="✖ Cancelar",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.BG_CARD_LIGHT,
            hover_color=Theme.DANGER,
            text_color=Theme.TEXT_MAIN,
            height=42,
            width=120,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._cancel_trim,
        )

        self.btn_trim = ctk.CTkButton(
            btn_row,
            text="✂️  RECORTAR TRECHO",
            font=Theme.FONT_BUTTON,
            fg_color="#D97706",
            hover_color="#B45309",
            text_color="#FFFFFF",
            height=42,
            corner_radius=Theme.CORNER_RADIUS_SM,
            state="disabled",
            command=self._start_trim,
        )
        self.btn_trim.pack(side="left", fill="x", expand=True)

    def _on_output_type_changed(self, value: str):
        is_audio = (value == "Áudio (MP3)")
        if self.source_info and self.source_info.source_type == "file":
            self.opt_quality.configure(state="disabled")
        else:
            self.opt_quality.configure(state="disabled" if is_audio else "normal")

    def _paste_source(self):
        try:
            text = self.clipboard_get().strip()
        except Exception:
            text = ""
        if text:
            self.entry_source.delete(0, "end")
            self.entry_source.insert(0, text)
            self._invalidate_source()

    def _select_local_file(self):
        exts = " ".join(f"*{ext}" for ext in sorted(ALL_SUPPORTED_EXTS))
        path = filedialog.askopenfilename(
            title="Selecionar vídeo ou áudio para recorte",
            filetypes=[("Arquivos de Mídia", exts), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.load_dropped_files([path])

    def load_dropped_files(self, paths: List[str]):
        """Aceita arquivos arrastados (Drag & Drop) diretamente na aba de Recorte Rápido."""
        if not paths or self.is_trimming:
            return
        for p in paths:
            if os.path.isfile(p) and os.path.splitext(p)[1].lower() in ALL_SUPPORTED_EXTS:
                self.entry_source.delete(0, "end")
                self.entry_source.insert(0, p)
                self._start_analysis()
                return
        self.lbl_source_info.configure(
            text="⚠️ Formato não suportado. Arraste um arquivo de vídeo ou áudio válido.",
            text_color=Theme.DANGER,
        )

    def _invalidate_source(self):
        self.source_info = None
        self.btn_open_folder.pack_forget()
        self.progress_bar.set(0.0)
        self.btn_trim.configure(state="disabled", text="✂️  RECORTAR TRECHO")
        self.lbl_source_info.configure(
            text="Clique em 'Analisar' para carregar a nova fonte.",
            text_color=Theme.TEXT_MUTED,
        )
        self.lbl_status.configure(
            text="Analise o novo link ou arquivo para liberar o recorte.",
            text_color=Theme.TEXT_MAIN,
        )

    def _update_clip_preview_label(self):
        start_s = parse_timestamp(self.entry_start.get())
        end_s = parse_timestamp(self.entry_end.get())
        total = self.source_info.duration_sec if self.source_info else 0.0
        ok, err = validate_trim_range(start_s, end_s, total)
        if ok and start_s is not None and end_s is not None:
            clip_len = end_s - start_s
            self.lbl_clip_duration.configure(
                text=f"⏱️ Trecho: {format_timestamp_hms(clip_len)}",
                text_color="#D97706",
            )
        else:
            self.lbl_clip_duration.configure(
                text=f"⚠️ {err[:52]}",
                text_color=Theme.DANGER,
            )

    def _start_analysis(self):
        if self.is_analyzing or self.is_trimming:
            return
        raw = self.entry_source.get().strip()
        if not raw:
            self.lbl_source_info.configure(
                text="⚠️ Cole um link ou selecione um arquivo local primeiro.",
                text_color=Theme.DANGER,
            )
            return

        self.is_analyzing = True
        self.source_info = None
        self.btn_open_folder.pack_forget()
        self.progress_bar.set(0.0)
        self.btn_trim.configure(state="disabled", text="✂️  RECORTAR TRECHO")
        self.btn_analyze.configure(state="disabled", text="⏳ Analisando...")
        self.lbl_source_info.configure(text="Analisando fonte...", text_color=Theme.TEXT_MUTED)
        self.lbl_status.configure(text="Carregando metadados da fonte...", text_color=Theme.TEXT_MUTED)

        def worker():
            info = analyze_trim_source(raw)
            self._safe_ui(self._finish_analysis, info)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_analysis(self, info: TrimSourceInfo):
        self.is_analyzing = False
        self.btn_analyze.configure(state="normal", text="🔍 Analisar")

        if info.error:
            self.source_info = None
            self.lbl_source_info.configure(text=f"✖ {info.error}", text_color=Theme.DANGER)
            self.lbl_status.configure(text="Não foi possível carregar a fonte.", text_color=Theme.DANGER)
            self.btn_trim.configure(state="disabled")
            return

        self.source_info = info
        dur_str = format_timestamp_hms(info.duration_sec) if info.duration_sec > 0 else "--:--:--"
        tag = "LOCAL" if info.source_type == "file" else (info.platform or "WEB").upper()
        short_title = (info.title[:58] + "...") if len(info.title) > 60 else info.title
        self.lbl_source_info.configure(
            text=f"✓ [{tag}] {short_title}  •  Duração total: {dur_str}",
            text_color=Theme.SUCCESS,
        )

        # Sempre reinicia Início/Fim para a nova fonte carregada (evita manter intervalo de vídeo anterior)
        self.entry_start.delete(0, "end")
        self.entry_start.insert(0, "00:00:00")
        self.entry_end.delete(0, "end")
        if info.duration_sec > 0:
            suggested_end = min(info.duration_sec, 60.0)
            self.entry_end.insert(0, format_timestamp_hms(suggested_end))
        else:
            self.entry_end.insert(0, "00:01:00")

        # Ajusta estado do seletor de qualidade e formato conforme tipo
        if info.source_type == "file":
            self.opt_quality.configure(state="disabled")
            if not info.is_video:
                self.var_output_type.set("Áudio (MP3)")
        else:
            if self.var_output_type.get() != "Áudio (MP3)":
                self.opt_quality.configure(state="normal")

        self._update_clip_preview_label()
        self.btn_trim.configure(state="normal")
        self.lbl_status.configure(
            text="Fonte pronta! Ajuste Início/Fim e clique em 'Recortar Trecho'.",
            text_color=Theme.TEXT_MAIN,
        )

    def _change_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            self.lbl_folder.configure(text=folder)
            update_setting("download_dir", folder)

    def _open_output_folder(self):
        if os.path.isdir(self.output_dir):
            if sys.platform == "win32":
                os.startfile(self.output_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.output_dir])
            else:
                subprocess.Popen(["xdg-open", self.output_dir])

    def _selected_max_height(self) -> Optional[int]:
        label = self.var_quality.get()
        for q_label, height in REMOTE_QUALITY_OPTIONS:
            if q_label == label:
                return height
        return None

    def _start_trim(self):
        if self.is_trimming or not self.source_info:
            return

        start_s = parse_timestamp(self.entry_start.get())
        end_s = parse_timestamp(self.entry_end.get())
        ok, err = validate_trim_range(start_s, end_s, self.source_info.duration_sec)
        if not ok or start_s is None or end_s is None:
            self.lbl_status.configure(text=f"⚠️ {err}", text_color=Theme.DANGER)
            return

        self.is_trimming = True
        self.btn_open_folder.pack_forget()
        self.btn_trim.configure(state="disabled", text="⏳ Recortando...")
        self.btn_analyze.configure(state="disabled")
        self.btn_cancel.pack(side="left", padx=(0, 8), before=self.btn_trim)
        self.progress_bar.set(0.02)
        self.lbl_status.configure(text="Iniciando recorte otimizado...", text_color=Theme.TEXT_MAIN)

        audio_only = (self.var_output_type.get() == "Áudio (MP3)")
        mode = TRIM_MODE_FAST
        max_height = self._selected_max_height()
        src = self.source_info

        def on_progress(pct: float, msg: str):
            self._safe_ui(self._update_progress, pct, msg)

        def worker():
            ok_trim, msg, out_path = self.trimmer.trim(
                source_info=src,
                start_sec=start_s,
                end_sec=end_s,
                output_dir=self.output_dir,
                audio_only=audio_only,
                mode=mode,
                max_height=max_height,
                on_progress=on_progress,
            )
            self._safe_ui(self._finish_trim, ok_trim, msg, out_path)

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, pct: float, msg: str):
        self.progress_bar.set(max(0.0, min(1.0, pct)))
        self.lbl_status.configure(text=msg, text_color=Theme.TEXT_MAIN)

    def _cancel_trim(self):
        if self.is_trimming:
            self.trimmer.cancel()
            self.lbl_status.configure(text="Cancelando recorte...", text_color=Theme.DANGER)

    def _finish_trim(self, ok: bool, msg: str, out_path: Optional[str]):
        self.is_trimming = False
        self.btn_cancel.pack_forget()
        self.btn_analyze.configure(state="normal")
        self.btn_trim.configure(state="normal", text="✂️  RECORTAR NOVAMENTE")

        if ok:
            self.progress_bar.set(1.0)
            self.lbl_status.configure(text=msg, text_color=Theme.SUCCESS)
            self.btn_open_folder.pack(side="left", padx=(0, 8), before=self.btn_trim)
            notify_async("Nexus Fetch — Recorte Concluído", msg)
        else:
            self.progress_bar.set(0.0)
            self.lbl_status.configure(text=f"✖ {msg}", text_color=Theme.DANGER)
