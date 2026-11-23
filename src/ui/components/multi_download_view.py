"""Tela de Multi-Download (Fila de 5 a 10 links) com análise prévia obrigatória antes do download."""
import os
import subprocess
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple
import tkinter.filedialog as fd
import customtkinter as ctk

from src.ui.theme import Theme
from src.core.metadata import MediaMetadata, extract_media_info
from src.core.downloader import MediaDownloader
from src.utils.validators import detect_platform
from src.utils.settings import get_setting, update_setting
from src.utils.notifications import notify_async
from src.utils.logger import log_error

INITIAL_FIELDS = 5
MAX_FIELDS = 10


def get_allowed_output_options(media_type: str) -> List[Tuple[str, str, str]]:
    """
    Retorna as opções de formato de saída permitidas para cada tipo de mídia,
    seguindo exatamente as mesmas regras das abas individuais:
    lista de (label_ui, mode, format_id).
    """
    if media_type == "image":
        return [("🖼️ Foto Original", "image", "photo_orig")]
    if media_type == "carousel":
        return [("🖼️ Mídias Originais", "image", "carousel_orig")]
    if media_type == "gif":
        return [
            ("🎞️ Animação (.GIF)", "gif", "gif_convert"),
            ("🎬 Vídeo (.MP4)", "video", "best"),
        ]
    if media_type == "audio":
        return [("🎵 Áudio (MP3)", "audio", "bestaudio/best")]
    # Padrão: vídeo ou playlist
    return [
        ("🎬 Vídeo (MP4)", "video", "bestvideo+bestaudio/best"),
        ("🎵 Áudio (MP3)", "audio", "bestaudio/best"),
    ]


@dataclass
class AnalyzedLinkItem:
    slot_index: int
    url: str
    platform: str
    metadata: Optional[MediaMetadata]
    error: Optional[str] = None
    selected_mode: str = "video"
    selected_format_id: str = "bestvideo+bestaudio/best"
    selected_label: str = "🎬 Vídeo (MP4)"

    def __post_init__(self):
        if self.metadata:
            opts = get_allowed_output_options(self.metadata.media_type)
            self.selected_label, self.selected_mode, self.selected_format_id = opts[0]

    @property
    def is_valid(self) -> bool:
        return self.metadata is not None and not self.metadata.error and not self.error


class MultiDownloadView(ctk.CTkFrame):
    """Interface para colar de 5 até 10 links, validar/analisar todos e baixar em lote."""

    def __init__(self, parent, app_instance=None):
        super().__init__(parent, fg_color="transparent")
        self.app_instance = app_instance
        self.downloader = MediaDownloader()
        self.is_analyzing = False
        self.is_downloading = False
        self._cancel_requested = False

        self.entries: List[ctk.CTkEntry] = []
        self.row_frames: List[ctk.CTkFrame] = []
        self.add_btn: Optional[ctk.CTkButton] = None
        self.analyzed_items: List[AnalyzedLinkItem] = []

        self.output_dir = get_setting("download_dir")

        self._build_ui()

    def _safe_ui(self, func, *args, **kwargs):
        if self.app_instance and hasattr(self.app_instance, "run_on_ui"):
            if kwargs:
                self.app_instance.run_on_ui(lambda: func(*args, **kwargs))
            else:
                self.app_instance.run_on_ui(func, *args)
        else:
            self.after(0, lambda: func(*args, **kwargs))

    def _build_ui(self):
        # 1. Card Explicativo
        intro = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.INFO,
        )
        intro.pack(fill="x", pady=(0, 10))

        intro_in = ctk.CTkFrame(intro, fg_color="transparent")
        intro_in.pack(fill="x", padx=18, pady=14)

        ctk.CTkLabel(
            intro_in,
            text="📋 Multi-Download (Fila de Links)",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_MAIN,
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            intro_in,
            text=(
                "Cole de 1 até 10 links (YouTube, Instagram ou Twitter/X). Clique primeiro em "
                "'Analisar Links' para conferir os títulos e validar cada link — só depois o botão de download será liberado."
            ),
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_NORMAL,
            justify="left",
            anchor="w",
            wraplength=760,
        ).pack(fill="x")

        # 2. Card de Campos de Links (5 iniciais, expansível até 10 com botão + no último campo)
        fields_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        fields_card.pack(fill="x", pady=(0, 10))

        fields_header = ctk.CTkFrame(fields_card, fg_color="transparent")
        fields_header.pack(fill="x", padx=16, pady=(12, 6))

        self.lbl_slots = ctk.CTkLabel(
            fields_header,
            text=f"Links na Fila ({INITIAL_FIELDS} de {MAX_FIELDS} campos)",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MAIN,
        )
        self.lbl_slots.pack(side="left")

        ctk.CTkButton(
            fields_header,
            text="🗑️ Limpar Campos",
            font=Theme.FONT_SMALL_BOLD,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.DANGER,
            text_color=Theme.TEXT_NORMAL,
            width=125,
            height=28,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._clear_all_fields,
        ).pack(side="right")

        self.fields_container = ctk.CTkFrame(fields_card, fg_color="transparent")
        self.fields_container.pack(fill="x", padx=16, pady=(0, 12))

        for _ in range(INITIAL_FIELDS):
            self._append_field_row()
        self._refresh_add_button_placement()

        # 3. Pasta de Destino (centralizada; o formato de saída é escolhido individualmente em cada item validado)
        opts_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        opts_card.pack(fill="x", pady=(0, 10))

        opts_in = ctk.CTkFrame(opts_card, fg_color="transparent")
        opts_in.pack(fill="x", padx=16, pady=12)

        row_dir = ctk.CTkFrame(opts_in, fg_color="transparent")
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
            width=120,
            height=30,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._choose_output_dir,
        ).pack(side="right")

        # 4. Botão Grandão de Análise + Painel de Revisão dos Links Analisados
        self.btn_analyze_all = ctk.CTkButton(
            self,
            text="🔍 ANALISAR LINKS",
            font=Theme.FONT_TITLE,
            fg_color=Theme.INFO,
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            height=44,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._start_analysis,
        )
        self.btn_analyze_all.pack(fill="x", pady=(0, 10))

        self.review_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        self.review_scroll = ctk.CTkScrollableFrame(
            self.review_card,
            fg_color=Theme.BG_DARK,
            corner_radius=Theme.CORNER_RADIUS_SM,
            height=120,
            scrollbar_button_color=Theme.SECONDARY,
            scrollbar_button_hover_color=Theme.SECONDARY_HOVER,
        )
        self.review_scroll.pack(fill="x", padx=12, pady=12)

        # 5. Barra de Progresso e Botão de Download (Bloqueado até analisar!)
        act_card = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_CARD,
            corner_radius=Theme.CORNER_RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        act_card.pack(fill="x", pady=(0, 6))

        act_in = ctk.CTkFrame(act_card, fg_color="transparent")
        act_in.pack(fill="x", padx=16, pady=14)

        self.lbl_status = ctk.CTkLabel(
            act_in,
            text="Cole os links e clique em 'Analisar Links' para liberar o download.",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_MAIN,
            anchor="w",
        )
        self.lbl_status.pack(fill="x", pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(
            act_in,
            fg_color=Theme.BG_INPUT,
            progress_color=Theme.PRIMARY,
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
            command=self._cancel_download,
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

        self.btn_download_all = ctk.CTkButton(
            btn_row,
            text="⚡ ANALISE OS LINKS PRIMEIRO",
            font=Theme.FONT_TITLE,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.PRIMARY_HOVER,
            text_color="#FFFFFF",
            height=42,
            corner_radius=Theme.CORNER_RADIUS_SM,
            state="disabled",
            command=self._start_batch_download,
        )
        self.btn_download_all.pack(side="right", fill="x", expand=True)

    def _append_field_row(self):
        idx = len(self.entries) + 1
        row = ctk.CTkFrame(self.fields_container, fg_color="transparent")
        row.pack(fill="x", pady=3)

        ctk.CTkLabel(
            row,
            text=f"#{idx:02d}",
            font=Theme.FONT_SMALL_BOLD,
            text_color=Theme.TEXT_NORMAL,
            width=30,
        ).pack(side="left", padx=(0, 6))

        entry = ctk.CTkEntry(
            row,
            placeholder_text=f"Cole o link #{idx} (YouTube, Instagram ou Twitter/X)...",
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BORDER_SUBTLE,
            text_color=Theme.TEXT_MAIN,
            height=36,
            corner_radius=Theme.CORNER_RADIUS_SM,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry.bind("<KeyRelease>", lambda e: self._invalidate_analysis())

        btn_paste = ctk.CTkButton(
            row,
            text="📋 Colar",
            font=Theme.FONT_BODY_BOLD,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            text_color=Theme.TEXT_MAIN,
            width=92,
            height=36,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=lambda ent=entry: self._paste_into_entry(ent),
        )
        btn_paste.pack(side="left")

        btn_remove = ctk.CTkButton(
            row,
            text="✖",
            font=Theme.FONT_BODY_BOLD,
            fg_color=Theme.BG_CARD_LIGHT,
            hover_color=Theme.DANGER,
            text_color=Theme.TEXT_NORMAL,
            border_width=1,
            border_color=Theme.BORDER_SUBTLE,
            width=36,
            height=36,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=lambda ent=entry: self.remove_link_field(self.entries.index(ent)),
        )
        btn_remove.pack(side="left", padx=(6, 0))

        self.entries.append(entry)
        self.row_frames.append(row)

    def remove_link_field(self, index: int) -> bool:
        """Remove o link na posição `index`, sobe os links de baixo reorganizando a fila e encolhe campos extras (>5)."""
        if self.is_analyzing or self.is_downloading:
            return False
        if not (0 <= index < len(self.entries)):
            return False

        # Captura os valores atuais removendo o índice escolhido
        values = [ent.get() for ent in self.entries]
        values.pop(index)

        # Se havia campos extras além dos 5 iniciais, remove a última linha sobrando
        if len(self.entries) > INITIAL_FIELDS:
            last_entry = self.entries.pop()
            last_row = self.row_frames.pop()
            last_row.destroy()
            del last_entry
        else:
            values.append("")

        for ent, val in zip(self.entries, values):
            ent.delete(0, "end")
            if val:
                ent.insert(0, val)

        self._refresh_add_button_placement()
        self._invalidate_analysis()
        return True

    def _refresh_add_button_placement(self):
        """Posiciona o botão '+' destacado exclusivamente no último campo (até o limite de 10)."""
        if self.add_btn is not None:
            self.add_btn.destroy()
            self.add_btn = None

        count = len(self.entries)
        self.lbl_slots.configure(text=f"Links na Fila ({count} de {MAX_FIELDS} campos)")

        if count < MAX_FIELDS and self.row_frames:
            last_row = self.row_frames[-1]
            self.add_btn = ctk.CTkButton(
                last_row,
                text="+",
                font=Theme.FONT_TITLE,
                fg_color=Theme.PRIMARY,
                hover_color=Theme.PRIMARY_HOVER,
                text_color="#FFFFFF",
                width=40,
                height=36,
                corner_radius=Theme.CORNER_RADIUS_SM,
                command=self.add_link_field,
            )
            self.add_btn.pack(side="left", padx=(6, 0))

    def add_link_field(self) -> bool:
        """Adiciona mais 1 campo de link (até o máximo de 10)."""
        if len(self.entries) >= MAX_FIELDS or self.is_analyzing or self.is_downloading:
            return False
        self._append_field_row()
        self._refresh_add_button_placement()
        return True

    def _paste_into_entry(self, entry: ctk.CTkEntry):
        try:
            clip = self.clipboard_get().strip()
            if clip:
                entry.delete(0, "end")
                entry.insert(0, clip)
                self._invalidate_analysis()
        except Exception:
            pass

    def _clear_all_fields(self):
        if self.is_analyzing or self.is_downloading:
            return
        for ent in self.entries:
            ent.delete(0, "end")
        self._invalidate_analysis()
        self.progress_bar.set(0.0)
        self.btn_open_folder.pack_forget()
        self.lbl_status.configure(
            text="Cole os links e clique em 'Analisar Links' para liberar o download.",
            text_color=Theme.TEXT_MAIN,
        )

    def _invalidate_analysis(self):
        """Sempre que qualquer campo mudar, bloqueia o download até nova análise."""
        if self.analyzed_items:
            self.analyzed_items.clear()
        if self.review_card.winfo_ismapped():
            self.review_card.pack_forget()
        self.btn_download_all.configure(
            state="disabled",
            text="⚡ ANALISE OS LINKS PRIMEIRO",
            fg_color=Theme.SECONDARY,
        )

    def _choose_output_dir(self):
        chosen = fd.askdirectory(initialdir=self.output_dir, title="Escolher Pasta de Destino")
        if chosen:
            self.output_dir = chosen
            self.lbl_dir.configure(text=chosen)
            update_setting("download_dir", chosen)

    def get_filled_urls(self) -> List[Tuple[int, str]]:
        """Retorna lista de (índice_1based, url) para todos os campos preenchidos."""
        filled = []
        for idx, ent in enumerate(self.entries, 1):
            val = ent.get().strip()
            if val:
                filled.append((idx, val))
        return filled

    def _start_analysis(self):
        if self.is_analyzing or self.is_downloading:
            return

        filled = self.get_filled_urls()
        if not filled:
            self.lbl_status.configure(
                text="⚠️ Cole pelo menos 1 link antes de analisar.",
                text_color=Theme.DANGER,
            )
            return

        self.is_analyzing = True
        self.analyzed_items.clear()
        self.btn_analyze_all.configure(state="disabled", text="⏳ ANALISANDO LINKS...")
        self.btn_download_all.configure(state="disabled", text="⏳ Aguarde a análise...", fg_color=Theme.SECONDARY)
        self.progress_bar.set(0.0)

        def worker():
            results: List[AnalyzedLinkItem] = []
            total = len(filled)
            for pos, (slot_idx, url) in enumerate(filled, 1):
                self._safe_ui(
                    self._update_analysis_progress,
                    (pos - 1) / total,
                    f"Analisando link #{slot_idx:02d} ({pos}/{total})...",
                )
                platform = detect_platform(url)
                if not platform:
                    results.append(
                        AnalyzedLinkItem(
                            slot_index=slot_idx,
                            url=url,
                            platform="desconhecido",
                            metadata=None,
                            error="Link inválido ou plataforma não suportada",
                        )
                    )
                    continue

                meta = extract_media_info(url)
                if meta and not meta.error:
                    results.append(
                        AnalyzedLinkItem(
                            slot_index=slot_idx,
                            url=url,
                            platform=platform,
                            metadata=meta,
                        )
                    )
                else:
                    results.append(
                        AnalyzedLinkItem(
                            slot_index=slot_idx,
                            url=url,
                            platform=platform,
                            metadata=meta,
                            error=(meta.error if meta else "Não foi possível obter metadados"),
                        )
                    )

            self._safe_ui(self._on_analysis_complete, results)

        threading.Thread(target=worker, daemon=True).start()

    def _update_analysis_progress(self, frac: float, msg: str):
        self.progress_bar.set(max(0.0, min(1.0, frac)))
        self.lbl_status.configure(text=msg, text_color=Theme.TEXT_MAIN)

    def _on_item_format_changed(self, item: AnalyzedLinkItem, chosen_label: str):
        """Atualiza o modo e format_id de saída escolhidos individualmente para o item."""
        if not item.metadata:
            return
        for lbl, mode, fmt_id in get_allowed_output_options(item.metadata.media_type):
            if lbl == chosen_label:
                item.selected_label = lbl
                item.selected_mode = mode
                item.selected_format_id = fmt_id
                break

    def _set_status_text(self, text: str):
        self.lbl_status.configure(text=text, text_color=Theme.TEXT_MAIN)

    def _on_analysis_complete(self, results: List[AnalyzedLinkItem]):
        self.is_analyzing = False
        self.analyzed_items = results
        self.btn_analyze_all.configure(state="normal", text="🔍 ANALISAR LINKS")
        self.progress_bar.set(1.0)

        # Renderiza lista de revisão com seletor individual de formato de saída por item
        for w in self.review_scroll.winfo_children():
            w.destroy()

        valid_count = 0
        for item in results:
            row = ctk.CTkFrame(
                self.review_scroll,
                fg_color=Theme.BG_CARD_LIGHT,
                corner_radius=Theme.CORNER_RADIUS_SM,
                border_width=1,
                border_color=Theme.SUCCESS if item.is_valid else Theme.DANGER,
            )
            row.pack(fill="x", pady=3, padx=4)

            if item.is_valid and item.metadata:
                valid_count += 1
                opts = get_allowed_output_options(item.metadata.media_type)
                opt_labels = [o[0] for o in opts]
                txt = f"✓ #{item.slot_index:02d}  [{item.platform.upper()}]  {item.metadata.title[:46]}  •  {item.metadata.duration_str}"

                ctk.CTkLabel(
                    row,
                    text=txt,
                    font=Theme.FONT_SMALL_BOLD,
                    text_color=Theme.SUCCESS,
                    anchor="w",
                ).pack(side="left", fill="x", expand=True, padx=(10, 6), pady=6)

                opt_menu = ctk.CTkOptionMenu(
                    row,
                    values=opt_labels,
                    font=Theme.FONT_SMALL_BOLD,
                    fg_color=Theme.BG_INPUT,
                    button_color=Theme.SECONDARY,
                    button_hover_color=Theme.SECONDARY_HOVER,
                    text_color=Theme.TEXT_MAIN,
                    width=165,
                    height=28,
                    state="normal" if len(opt_labels) > 1 else "disabled",
                    command=lambda val, it=item: self._on_item_format_changed(it, val),
                )
                opt_menu.set(item.selected_label)
                opt_menu.pack(side="right", padx=(4, 8), pady=4)
            else:
                txt = f"✖ #{item.slot_index:02d}  {item.error or 'Link inválido'}"
                ctk.CTkLabel(
                    row,
                    text=txt,
                    font=Theme.FONT_SMALL_BOLD,
                    text_color=Theme.DANGER,
                    anchor="w",
                ).pack(fill="x", padx=10, pady=6)

        if not self.review_card.winfo_ismapped():
            self.review_card.pack(fill="x", pady=(0, 10), after=self.btn_analyze_all)

        if valid_count > 0:
            self.btn_download_all.configure(
                state="normal",
                text=f"⚡ BAIXAR {valid_count} LINK{'S' if valid_count != 1 else ''} VÁLIDO{'S' if valid_count != 1 else ''}",
                fg_color=Theme.PRIMARY,
            )
            self.lbl_status.configure(
                text=f"✓ Análise concluída: {valid_count} de {len(results)} link(s) válido(s). Escolha o formato de cada item acima e clique em Baixar!",
                text_color=Theme.SUCCESS,
            )
        else:
            self.btn_download_all.configure(
                state="disabled",
                text="✖ NENHUM LINK VÁLIDO ENCONTRADO",
                fg_color=Theme.SECONDARY,
            )
            self.lbl_status.configure(
                text="✖ Nenhum link válido foi encontrado. Corrija os links e analise novamente.",
                text_color=Theme.DANGER,
            )

    def _start_batch_download(self):
        valid_items = [it for it in self.analyzed_items if it.is_valid and it.metadata]
        if not valid_items or self.is_downloading:
            return

        self.is_downloading = True
        self._cancel_requested = False
        self.progress_bar.set(0.0)
        self.btn_open_folder.pack_forget()
        self.btn_cancel.pack(side="left", padx=(0, 10))
        self.btn_analyze_all.configure(state="disabled")
        self.btn_download_all.configure(state="disabled", text="Baixando fila...", fg_color=Theme.SECONDARY)

        def worker():
            total = len(valid_items)
            ok_count = 0

            for idx, item in enumerate(valid_items, 1):
                if self._cancel_requested:
                    self._safe_ui(
                        self._on_batch_complete,
                        False,
                        f"Fila cancelada ({ok_count}/{total} baixados).",
                    )
                    return

                meta = item.metadata
                done_evt = threading.Event()
                item_ok = [False]

                def on_prog(pct, spd, eta, fname, i=idx, m=meta):
                    overall = ((i - 1) / total) + ((pct / 100.0) / total)
                    self._safe_ui(
                        self._update_analysis_progress,
                        overall,
                        f"[{i}/{total}] {m.title[:42]} • {pct:.0f}% ({spd})",
                    )

                def on_stat(msg, i=idx):
                    self._safe_ui(self._set_status_text, f"[{i}/{total}] {msg}")

                def on_done(ok, msg, path, m=meta):
                    item_ok[0] = ok
                    if not ok:
                        log_error(f"Multi-Download falhou em {m.url}: {msg}")
                    done_evt.set()

                self._safe_ui(
                    self._update_analysis_progress,
                    (idx - 1) / total,
                    f"[{idx}/{total}] Iniciando: {meta.title[:45]}...",
                )

                self.downloader.download_async(
                    url=meta.url,
                    output_dir=self.output_dir,
                    mode=item.selected_mode,
                    format_id=item.selected_format_id,
                    media_type=meta.media_type,
                    image_urls=meta.image_urls,
                    title=meta.title,
                    playlist_items=meta.playlist_items if meta.is_playlist else None,
                    on_progress=on_prog,
                    on_status=on_stat,
                    on_complete=on_done,
                )
                done_evt.wait()
                if item_ok[0]:
                    ok_count += 1

            self._safe_ui(
                self._on_batch_complete,
                ok_count > 0,
                f"Fila concluída! {ok_count} de {total} link(s) baixado(s) com sucesso.",
            )

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_download(self):
        self._cancel_requested = True
        self.downloader.cancel()
        self.lbl_status.configure(text="Cancelando fila de downloads...")

    def _on_batch_complete(self, success: bool, msg: str):
        self.is_downloading = False
        self.btn_cancel.pack_forget()
        self.btn_analyze_all.configure(state="normal")
        self.btn_download_all.configure(state="normal", text="⚡ BAIXAR NOVAMENTE", fg_color=Theme.PRIMARY)

        if success:
            self.progress_bar.set(1.0)
            self.lbl_status.configure(text=f"✓ {msg}", text_color=Theme.SUCCESS)
            self.btn_open_folder.pack(side="left", padx=(0, 10))
            notify_async("Nexus Fetch — Multi-Download Concluído", msg)
        else:
            self.lbl_status.configure(text=f"✖ {msg}", text_color=Theme.DANGER)

    def _open_output_folder(self):
        if os.path.exists(self.output_dir):
            if os.name == "nt":
                os.startfile(self.output_dir)
            else:
                subprocess.run(["xdg-open", self.output_dir])
