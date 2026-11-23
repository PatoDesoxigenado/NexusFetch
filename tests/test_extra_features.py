"""Testes de funcionalidade e interface para Preferências, Notificações, Compressor, Multi-Download e Menu ☰."""
import os
import sys
import json
from unittest.mock import patch, MagicMock
import pytest
import customtkinter as ctk

from src.config import MODULE_COMPRESSOR, MODULE_MULTI_DOWNLOAD
from src.core.converter import MediaFileInfo
from src.core.compressor import calculate_compression_plan, PRESET_BY_KEY
from src.core.metadata import MediaMetadata
from src.utils import settings as settings_mod
from src.utils import notifications as notif_mod
from src.ui.components.navbar import NavBar
from src.ui.components.compressor_view import CompressorView
from src.ui.components.multi_download_view import (
    MultiDownloadView,
    AnalyzedLinkItem,
    get_allowed_output_options,
    INITIAL_FIELDS,
    MAX_FIELDS,
)


# ------------------------------------------------------------------
# 1. Persistência de Preferências (settings.json)
# ------------------------------------------------------------------

def test_settings_persistence_and_corrupt_recovery(tmp_path):
    sf = tmp_path / "settings.json"
    with patch.object(settings_mod, "SETTINGS_FILE", str(sf)):
        # Padrões quando não existe
        defaults = settings_mod.load_settings()
        assert defaults["theme"] == "dark"
        assert defaults["notifications_enabled"] is True

        # Salva e recarrega
        assert settings_mod.update_setting("theme", "light") is True
        assert settings_mod.update_setting("preferred_quality", "1080p") is True
        assert settings_mod.get_setting("theme") == "light"
        assert settings_mod.get_setting("preferred_quality") == "1080p"

        # Recupera de JSON corrompido sem quebrar
        sf.write_text("{corrupted json", encoding="utf-8")
        recovered = settings_mod.load_settings()
        assert recovered["theme"] == "dark"


# ------------------------------------------------------------------
# 2. Notificações Nativas do SO
# ------------------------------------------------------------------

def test_native_notification_respects_flag_and_platform():
    with patch("src.utils.notifications.subprocess.Popen") as mock_popen:
        assert notif_mod.send_native_notification("T", "M", enabled=False) is False
        assert not mock_popen.called

        if sys.platform == "win32":
            assert notif_mod.send_native_notification("Nexus Fetch", "Pronto!", enabled=True) is True
            assert mock_popen.called
            cmd = mock_popen.call_args[0][0]
            assert "powershell" in cmd[0].lower()


# ------------------------------------------------------------------
# 3. Motor do Compressor (Discord & WhatsApp — Vídeo e Áudio)
# ------------------------------------------------------------------

def test_compressor_plan_skips_when_already_within_limit():
    small_vid = MediaFileInfo(
        path="small.mp4", name="small.mp4",
        size_bytes=5 * 1024 * 1024, size_str="5.0 MB",
        is_video=True, is_audio=False, ext=".mp4",
        duration_sec=30.0, duration_str="00:30", width=1920, height=1080,
    )
    _, limit_mb, target_mb = PRESET_BY_KEY["discord_10"]
    plan = calculate_compression_plan(small_vid, limit_mb, target_mb)
    assert plan.already_within_limit is True


def test_compressor_plan_video_discord_and_whatsapp():
    big_vid = MediaFileInfo(
        path="big.mp4", name="big.mp4",
        size_bytes=120 * 1024 * 1024, size_str="120.0 MB",
        is_video=True, is_audio=False, ext=".mp4",
        duration_sec=120.0, duration_str="02:00", width=3840, height=2160,
    )
    _, limit_mb, target_mb = PRESET_BY_KEY["discord_10"]
    plan = calculate_compression_plan(big_vid, limit_mb, target_mb)
    assert plan.already_within_limit is False
    assert plan.is_video is True
    assert plan.output_ext == ".mp4"
    assert plan.video_kbps >= 150
    assert plan.audio_kbps in (64, 96, 128)
    # 120s em ~9.4 MB -> ~600 kbps total -> downscale adaptativo + 30fps para preservar nitidez
    assert plan.scale_height in (480, 720)
    assert plan.target_fps == 30

    # Vídeo extremamente longo (12 min) para 10 MB deve sinalizar aviso de qualidade baixa
    very_long = MediaFileInfo(
        path="long.webm", name="long.webm",
        size_bytes=4 * 1024 * 1024 * 1024, size_str="4.0 GB",
        is_video=True, is_audio=False, ext=".webm",
        duration_sec=723.0, duration_str="12:03", width=3840, height=2160,
    )
    plan_long = calculate_compression_plan(very_long, limit_mb, target_mb)
    assert plan_long.low_quality_warning is True
    assert plan_long.target_fps == 30


def test_compressor_plan_audio_discord():
    big_wav = MediaFileInfo(
        path="track.wav", name="track.wav",
        size_bytes=45 * 1024 * 1024, size_str="45.0 MB",
        is_video=False, is_audio=True, ext=".wav",
        duration_sec=300.0, duration_str="05:00",
    )
    _, limit_mb, target_mb = PRESET_BY_KEY["discord_10"]
    plan = calculate_compression_plan(big_wav, limit_mb, target_mb)
    assert plan.already_within_limit is False
    assert plan.is_video is False
    assert plan.output_ext == ".mp3"
    assert 48 <= plan.audio_kbps <= 320
    assert plan.video_kbps == 0


# ------------------------------------------------------------------
# 4. Testes de Interface (NavBar ☰, MultiDownloadView, CompressorView)
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def ctk_root():
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_ui_navbar_more_menu_and_theme_moved(ctk_root, tmp_path):
    sf = tmp_path / "settings.json"
    selected = []
    with patch.object(settings_mod, "SETTINGS_FILE", str(sf)):
        nav = NavBar(ctk_root, on_module_selected=lambda m: selected.append(m))
        try:
            # Botão de tema não fica mais solto na navbar; agora existe btn_more ("☰")
            assert not hasattr(nav, "btn_theme")
            assert hasattr(nav, "btn_more")
            assert nav.btn_more.cget("text") == "☰"

            # Seleção via menu suspenso
            nav._select_from_menu(MODULE_COMPRESSOR)
            assert selected[-1] == MODULE_COMPRESSOR
            assert nav.current_module == MODULE_COMPRESSOR

            nav._select_from_menu(MODULE_MULTI_DOWNLOAD)
            assert selected[-1] == MODULE_MULTI_DOWNLOAD

            # Alternância de tema persiste em settings.json
            before = ctk.get_appearance_mode().lower()
            nav._toggle_theme()
            after = ctk.get_appearance_mode().lower()
            assert after != before
            assert settings_mod.get_setting("theme") == after
        finally:
            nav.destroy()


def test_ui_multi_download_fields_expansion_and_analysis_gate(ctk_root):
    view = MultiDownloadView(ctk_root)
    try:
        # Inicia com exatamente 5 campos e botão '+' no último
        assert len(view.entries) == INITIAL_FIELDS == 5
        assert view.add_btn is not None
        # Botão de download começa bloqueado até analisar
        assert view.btn_download_all.cget("state") == "disabled"

        # Adiciona até 5 campos extras (total 10)
        for expected in range(6, MAX_FIELDS + 1):
            assert view.add_link_field() is True
            assert len(view.entries) == expected

        # Não permite ultrapassar 10 campos e oculta '+'
        assert view.add_link_field() is False
        assert len(view.entries) == 10
        assert view.add_btn is None

        # Simula análise concluída com 1 link válido -> libera botão de download
        fake_meta = MediaMetadata(
            url="https://www.youtube.com/watch?v=abc",
            title="Vídeo Teste",
            uploader="Canal",
            duration=60,
            duration_str="01:00",
            thumbnail_url=None,
        )
        view._on_analysis_complete([
            AnalyzedLinkItem(slot_index=1, url=fake_meta.url, platform="youtube", metadata=fake_meta)
        ])
        assert view.btn_download_all.cget("state") == "normal"

        # Alterar qualquer campo trava o download de volta até reanalisar
        view._invalidate_analysis()
        assert view.btn_download_all.cget("state") == "disabled"
        # Não existe mais seletor global de formato na aba Multi-Download
        assert not hasattr(view, "seg_format")
    finally:
        view.destroy()


def test_multi_download_per_item_format_rules_and_safe_ui_callback(ctk_root):
    # Regras de saída por tipo de mídia
    vid_opts = [m for _, m, _ in get_allowed_output_options("video")]
    assert vid_opts == ["video", "audio"]
    gif_opts = [m for _, m, _ in get_allowed_output_options("gif")]
    assert gif_opts == ["gif", "video"]
    img_opts = [m for _, m, _ in get_allowed_output_options("image")]
    assert img_opts == ["image"]
    car_opts = [m for _, m, _ in get_allowed_output_options("carousel")]
    assert car_opts == ["image"]

    view = MultiDownloadView(ctk_root)
    try:
        meta_vid = MediaMetadata(
            url="https://youtu.be/abc", title="Vid", uploader="Ch",
            duration=10, duration_str="00:10", thumbnail_url=None, media_type="video",
        )
        meta_img = MediaMetadata(
            url="https://x.com/u/status/1", title="Foto", uploader="U",
            duration=0, duration_str="Foto", thumbnail_url=None, media_type="image",
        )
        item_vid = AnalyzedLinkItem(slot_index=1, url=meta_vid.url, platform="youtube", metadata=meta_vid)
        item_img = AnalyzedLinkItem(slot_index=2, url=meta_img.url, platform="twitter", metadata=meta_img)
        # Usuário escolhe baixar o vídeo como MP3 individualmente
        view._on_item_format_changed(item_vid, "🎵 Áudio (MP3)")
        assert item_vid.selected_mode == "audio"
        assert item_img.selected_mode == "image"

        # Garante que _safe_ui aceita kwargs sem lançar TypeError (causa do bug 0/6 anterior)
        view._safe_ui(view.lbl_status.configure, text="Teste OK")

        # Testa botão '✖' removendo o item #5 e subindo o #6 (reorganizando a ordem)
        view.add_link_field()  # 6 campos
        for i, url in enumerate(["u1", "u2", "u3", "u4", "u5_bad", "u6_good"]):
            view.entries[i].insert(0, url)
        assert view.remove_link_field(4) is True  # remove #05 ("u5_bad")
        assert len(view.entries) == 5
        assert [e.get() for e in view.entries] == ["u1", "u2", "u3", "u4", "u6_good"]
        assert view.add_btn is not None  # botão '+' restaurado no último campo
    finally:
        view.destroy()


def test_ui_compressor_view_presets_and_initial_state(ctk_root):
    view = CompressorView(ctk_root)
    try:
        assert view.btn_compress.cget("state") == "disabled"
        assert view.selected_preset_key == "discord_10"

        view._on_preset_changed(PRESET_BY_KEY["whatsapp_16"][0])
        assert view.selected_preset_key == "whatsapp_16"

        view._on_preset_changed(PRESET_BY_KEY["whatsapp_64"][0])
        assert view.selected_preset_key == "whatsapp_64"
    finally:
        view.destroy()
