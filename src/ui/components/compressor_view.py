"""Interface da aba Compressor de Mídia por Tamanho Alvo (Discord & WhatsApp)."""
import os
import subprocess
import threading
from typing import List, Optional
import tkinter.filedialog as fd
import customtkinter as ctk

from src.ui.theme import Theme
from src.core.converter import MediaFileInfo, probe_media_file, ALL_SUPPORTED_EXTS
from src.core.compressor import (
    COMPRESS_PRESETS,
    PRESET_BY_KEY,
    MediaCompressor,
    calculate_compression_plan,
)
from src.utils.settings import get_setting, update_setting
from src.utils.notifications import notify_async


class CompressorView(ctk.CTkFrame):
    """Tela dedicada à compressão inteligente de vídeos e áudios para caber no Discord ou WhatsApp."""

    def __init__(self, parent, app_instance=None):
        super().__init__(parent, fg_color="transparent")
        self.app_instance = app_instance
        self.compressor = MediaCompressor()
        self.files: List[MediaFileInfo] = []
        self.is_compressing = False
        self.output_dir = get_setting("converter_output_dir")
        self.selected_preset_key = COMPRESS_PRESETS[0][0]
        self._label_to_key = {label: key for key, label, _, _ in COMPRESS_PRESETS}

        self._build_ui()

    def _safe_ui(self, func, *args):
        if self.app_instance and hasattr(self.app_instance, "run_on_ui"):
            self.app_instance.run_on_ui(func, *args)
        else:
            self.after(0, lambda: func(*args))

    def _build_ui(self):
        # 1. Card Explicativo
        intro = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color="#059669",
        )
        intro.pack(fill="x", pady=(0, 10))

        intro_in = ctk.CTkFrame(intro, fg_color="transparent")
        intro_in.pack(fill="x", padx=18, pady=14)

        ctk.CTkLabel(
            intro_in,
            text="📦 Compressor Inteligente (Discord & WhatsApp)",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN,
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            intro_in,
            text=(
                "Reduz vídeos e áudios grandes para caberem exatamente no limite do Discord ou WhatsApp "
                "usando codificação H.264 em 2 passos (2-Pass) e ajuste adaptativo para preservar máxima nitidez."
            ),
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_NORMAL,
            justify="left",
            anchor="w",
            wraplength=760,
        ).pack(fill="x")

        # 2. Área de Seleção de Arquivos
        drop_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        drop_card.pack(fill="x", pady=(0, 10))

        drop_in = ctk.CTkFrame(drop_card, fg_color="transparent")
        drop_in.pack(fill="x", padx=16, pady=14)

        top_bar = ctk.CTkFrame(drop_in, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 8))

        self.lbl_queue_title = ctk.CTkLabel(
            top_bar,
            text="Arquivos para Comprimir (0)",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MAIN,
        )
        self.lbl_queue_title.pack(side="left")

        btn_clear = ctk.CTkButton(
            top_bar,
            text="🗑️ Limpar",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.DANGER,
            text_color=Theme.TEXT_NORMAL,
            width=90,
            height=30,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._clear_files,
        )
        btn_clear.pack(side="right", padx=(6, 0))

        self.btn_add_files = ctk.CTkButton(
            top_bar,
            text="📂 Selecionar Vídeos / Áudios",
            font=Theme.FONT_BUTTON,
            fg_color="#059669",
            hover_color="#10B981",
            text_color="#FFFFFF",
            height=32,
            width=210,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._browse_files,
        )
        self.btn_add_files.pack(side="right")

        self.files_scroll = ctk.CTkScrollableFrame(
            drop_in,
            fg_color=Theme.BG_DARK,
            corner_radius=Theme.CORNER_RADIUS_SM,
            height=135,
            scrollbar_button_color=Theme.SECONDARY,
            scrollbar_button_hover_color=Theme.SECONDARY_HOVER,
        )
        self.files_scroll.pack(fill="x")
        self._render_files_list()

        # 3. Card de Configurações (Preset + Pasta)
        cfg_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        cfg_card.pack(fill="x", pady=(0, 10))

        cfg_in = ctk.CTkFrame(cfg_card, fg_color="transparent")
        cfg_in.pack(fill="x", padx=16, pady=14)

        row_preset = ctk.CTkFrame(cfg_in, fg_color="transparent")
        row_preset.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            row_preset,
            text="APLICATIVO / LIMITE ALVO:",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_NORMAL,
        ).pack(side="left", padx=(0, 12))

        preset_labels = [lbl for _, lbl, _, _ in COMPRESS_PRESETS]
        self.opt_preset = ctk.CTkOptionMenu(
            row_preset,
            values=preset_labels,
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_INPUT,
            button_color=Theme.SECONDARY,
            button_hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_MAIN,
            height=34,
            width=340,
            command=self._on_preset_changed,
        )
        self.opt_preset.set(preset_labels[0])
        self.opt_preset.pack(side="left")

        row_dir = ctk.CTkFrame(cfg_in, fg_color="transparent")
        row_dir.pack(fill="x")

        ctk.CTkLabel(
            row_dir,
            text="SALVAR EM:",
            font=Theme.FONT_BADGE,
            text_color=Theme.TEXT_NORMAL,
        ).pack(side="left", padx=(0, 10))

        self.lbl_dir = ctk.CTkLabel(
            row_dir,
            text=self.output_dir,
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_MAIN,
            anchor="w",
        )
        self.lbl_dir.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            row_dir,
            text="📁 Alterar Pasta",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_NORMAL,
            width=115,
            height=28,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._choose_output_dir,
        ).pack(side="right")

        # 4. Rodapé de Progresso e Ação
        act_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        act_card.pack(fill="x")

        act_in = ctk.CTkFrame(act_card, fg_color="transparent")
        act_in.pack(fill="x", padx=16, pady=14)

        self.lbl_status = ctk.CTkLabel(
            act_in,
            text="Adicione vídeos ou áudios acima para comprimir.",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MAIN,
            anchor="w",
        )
        self.lbl_status.pack(fill="x", pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(
            act_in,
            fg_color=Theme.BG_INPUT,
            progress_color="#059669",
            height=10,
            corner_radius=Theme.CORNER_RADIUS_SM,
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(0, 12))

        btn_row = ctk.CTkFrame(act_in, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_cancel = ctk.CTkButton(
            btn_row,
            text="✖ Cancelar",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.DANGER,
            width=120,
            height=42,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._cancel_compression,
        )

        self.btn_open_folder = ctk.CTkButton(
            btn_row,
            text="📂 Abrir Pasta",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            text_color="#FFFFFF",
            width=135,
            height=42,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._open_output_folder,
        )

        self.btn_compress = ctk.CTkButton(
            btn_row,
            text="📦 COMPRIMIR ARQUIVOS",
            font=Theme.FONT_TITLE,
            fg_color="#059669",
            hover_color="#10B981",
            text_color="#FFFFFF",
            height=42,
            corner_radius=Theme.CORNER_RADIUS_SM,
            state="disabled",
            command=self._start_compression,
        )
        self.btn_compress.pack(side="right", fill="x", expand=True)

    def _browse_files(self):
        exts = " ".join(f"*{e}" for e in sorted(ALL_SUPPORTED_EXTS))
        selected = fd.askopenfilenames(
            title="Selecionar Vídeos ou Áudios para Comprimir",
            filetypes=[("Arquivos de Mídia", exts), ("Todos os Arquivos", "*.*")],
        )
        if selected:
            self.add_files(list(selected))

    def add_files(self, paths: List[str]):
        existing = {f.path for f in self.files}
        new_paths = [p for p in paths if os.path.isfile(p) and p not in existing]
        if not new_paths:
            return

        self.lbl_status.configure(text="Analisando arquivos selecionados...", text_color=Theme.TEXT_MAIN)

        def worker():
            probed = []
            for p in new_paths:
                ext = os.path.splitext(p)[1].lower()
                if ext in ALL_SUPPORTED_EXTS:
                    info = probe_media_file(p)
                    if info:
                        probed.append(info)
            self._safe_ui(self._on_files_probed, probed)

        threading.Thread(target=worker, daemon=True).start()

    def _on_files_probed(self, probed: List[MediaFileInfo]):
        self.files.extend(probed)
        self._render_files_list()
        if self.files:
            self.btn_compress.configure(state="normal")
            self.lbl_status.configure(
                text=f"{len(self.files)} arquivo(s) pronto(s) para análise e compressão.",
                text_color=Theme.TEXT_MAIN,
            )

    def _clear_files(self):
        if self.is_compressing:
            return
        self.files.clear()
        self._render_files_list()
        self.progress_bar.set(0.0)
        self.btn_open_folder.pack_forget()
        self.btn_compress.configure(state="disabled")
        self.lbl_status.configure(text="Adicione vídeos ou áudios acima para comprimir.", text_color=Theme.TEXT_MAIN)

    def _on_preset_changed(self, label: str):
        self.selected_preset_key = self._label_to_key.get(label, "discord_10")
        self._render_files_list()

    def _choose_output_dir(self):
        chosen = fd.askdirectory(initialdir=self.output_dir, title="Escolher Pasta de Saída")
        if chosen:
            self.output_dir = chosen
            self.lbl_dir.configure(text=chosen)
            update_setting("converter_output_dir", chosen)

    def _render_files_list(self):
        for w in self.files_scroll.winfo_children():
            w.destroy()

        self.lbl_queue_title.configure(text=f"Arquivos para Comprimir ({len(self.files)})")
        if not self.files:
            empty_lbl = ctk.CTkLabel(
                self.files_scroll,
                text="📂 Arraste e solte seus vídeos ou áudios aqui\n(ou clique nesta área / no botão acima para selecionar múltiplos arquivos)",
                font=Theme.FONT_BODY,
                text_color=Theme.TEXT_DIM,
                cursor="hand2",
            )
            empty_lbl.pack(pady=35)
            empty_lbl.bind("<Button-1>", lambda e: self._browse_files())
            return

        _, limit_mb, target_mb = PRESET_BY_KEY[self.selected_preset_key]
        for idx, finfo in enumerate(self.files):
            plan = calculate_compression_plan(finfo, limit_mb, target_mb)
            row = ctk.CTkFrame(
                self.files_scroll,
                fg_color=Theme.BG_CARD_LIGHT,
                corner_radius=Theme.CORNER_RADIUS_SM,
                border_width=1,
                border_color=Theme.BORDER_SUBTLE,
            )
            row.pack(fill="x", pady=2, padx=4)

            icon = "🎬" if finfo.is_video else "🎵"
            if plan.already_within_limit:
                status_txt = f"✓ Já cabe ({finfo.size_str})"
                status_col = Theme.SUCCESS
            elif plan.low_quality_warning:
                status_txt = f"⚠️ Muito longo ({finfo.duration_str}) p/ {limit_mb:.0f} MB — qualidade baixa"
                status_col = Theme.DANGER
            else:
                status_txt = f"⚡ {finfo.size_str} ➔ ~{target_mb:.1f} MB"
                status_col = "#F59E0B"

            ctk.CTkLabel(
                row,
                text=f"{icon}  {finfo.name[:44]}",
                font=Theme.FONT_BODY,
                text_color=Theme.TEXT_MAIN,
                anchor="w",
            ).pack(side="left", padx=10, pady=6, fill="x", expand=True)

            ctk.CTkLabel(
                row,
                text=status_txt,
                font=Theme.FONT_SMALL_BOLD,
                text_color=status_col,
            ).pack(side="right", padx=10)

            ctk.CTkButton(
                row,
                text="✖",
                width=26,
                height=24,
                fg_color="transparent",
                hover_color=Theme.DANGER,
                text_color=Theme.TEXT_DIM,
                command=lambda i=idx: self._remove_file(i),
            ).pack(side="right", padx=(0, 4))

    def _remove_file(self, idx: int):
        if self.is_compressing:
            return
        if 0 <= idx < len(self.files):
            self.files.pop(idx)
            self._render_files_list()
            if not self.files:
                self.btn_compress.configure(state="disabled")

    def _start_compression(self):
        if not self.files or self.is_compressing:
            return
        self.is_compressing = True
        self.progress_bar.set(0.0)
        self.btn_open_folder.pack_forget()
        self.btn_cancel.pack(side="left", padx=(0, 10))
        self.btn_compress.configure(state="disabled", text="Comprimindo...")
        self.btn_add_files.configure(state="disabled")

        self.compressor.compress_batch_async(
            files=list(self.files),
            preset_key=self.selected_preset_key,
            output_dir=self.output_dir,
            on_progress=lambda pct, msg: self._safe_ui(self._on_progress, pct, msg),
            on_complete=lambda ok, msg, out_dir: self._safe_ui(self._on_complete, ok, msg, out_dir),
        )

    def _cancel_compression(self):
        self.compressor.cancel()
        self.lbl_status.configure(text="Cancelando compressão...")

    def _on_progress(self, pct: float, msg: str):
        self.progress_bar.set(max(0.0, min(1.0, pct / 100.0)))
        self.lbl_status.configure(text=msg, text_color=Theme.TEXT_MAIN)

    def _on_complete(self, success: bool, msg: str, out_dir: str):
        self.is_compressing = False
        self.btn_cancel.pack_forget()
        self.btn_add_files.configure(state="normal")
        self.btn_compress.configure(state="normal", text="📦 COMPRIMIR ARQUIVOS")

        if success:
            self.progress_bar.set(1.0)
            self.lbl_status.configure(text=f"✓ {msg}", text_color=Theme.SUCCESS)
            self.btn_open_folder.pack(side="left", padx=(0, 10))
            notify_async("Nexus Fetch — Compressão Concluída", msg)
        else:
            self.lbl_status.configure(text=f"✖ {msg}", text_color=Theme.DANGER)

    def _open_output_folder(self):
        if os.path.exists(self.output_dir):
            if os.name == "nt":
                os.startfile(self.output_dir)
            else:
                subprocess.run(["xdg-open", self.output_dir])
