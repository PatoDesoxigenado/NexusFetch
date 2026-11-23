"""Testes unitários, de motor FFmpeg local e de interface para o Recorte Rápido (Trim / Clip)."""
import os
import subprocess
import pytest
import customtkinter as ctk

from src.config import MODULE_TRIMMER
from src.core.converter import get_ffmpeg_executable, probe_media_file
from src.core.trimmer import (
    MediaTrimmer,
    TrimSourceInfo,
    TRIM_MODE_FAST,
    TRIM_MODE_PRECISE,
    parse_timestamp,
    format_timestamp_hms,
    format_timestamp_slug,
    validate_trim_range,
    build_local_trim_command,
    build_remote_trim_command,
)
from src.ui.components.trimmer_view import TrimmerView
from src.ui.components.navbar import NavBar


def test_parse_and_format_timestamps():
    assert parse_timestamp("00:00:00") == 0.0
    assert parse_timestamp("00:02:00") == 120.0
    assert parse_timestamp("2:14:46") == 2 * 3600 + 14 * 60 + 46
    assert parse_timestamp("01:30") == 90.0
    assert parse_timestamp("45.5") == 45.5
    assert parse_timestamp("") is None
    assert parse_timestamp("-5") is None
    assert parse_timestamp("00:75") is None
    assert parse_timestamp("abc") is None

    assert format_timestamp_hms(120) == "00:02:00"
    assert format_timestamp_hms(2 * 3600 + 14 * 60 + 46) == "02:14:46"
    assert format_timestamp_slug(120) == "02m00s"
    assert format_timestamp_slug(3665) == "01h01m05s"


def test_validate_trim_range():
    ok, _ = validate_trim_range(0.0, 120.0, 8086.0)
    assert ok is True

    ok_inv, msg_inv = validate_trim_range(120.0, 60.0, 8086.0)
    assert ok_inv is False
    assert "maior" in msg_inv.lower()

    ok_over, msg_over = validate_trim_range(0.0, 9000.0, 8086.0)
    assert ok_over is False
    assert "ultrapassa" in msg_over.lower()


def test_remote_command_uses_input_seeking_before_i():
    """Garante que -ss e -t vêm ANTES de cada -i para nunca baixar o vídeo completo."""
    cmd, label = build_remote_trim_command(
        ffmpeg_exe="ffmpeg",
        video_url="https://example.com/video.mp4",
        audio_url="https://example.com/audio.m4a",
        output_path="out.mp4",
        start_sec=3600.0,
        duration_sec=120.0,
        headers={"User-Agent": "TestAgent"},
        audio_only=False,
        mode=TRIM_MODE_FAST,
    )
    assert label == "Stream Copy"
    # Verifica que -ss precede -i para ambos os inputs (video e audio)
    i_indices = [idx for idx, tok in enumerate(cmd) if tok == "-i"]
    ss_indices = [idx for idx, tok in enumerate(cmd) if tok == "-ss"]
    assert len(i_indices) == 2
    assert len(ss_indices) == 2
    assert ss_indices[0] < i_indices[0]
    assert ss_indices[1] < i_indices[1]
    assert "-c" in cmd and "copy" in cmd


def test_local_trim_real_ffmpeg(tmp_path):
    """Gera um vídeo sintético de 10s e recorta 3s (00:00:02 -> 00:00:05) validando com ffprobe."""
    ffmpeg = get_ffmpeg_executable()
    if not ffmpeg:
        pytest.skip("FFmpeg indisponível no ambiente")

    src_video = str(tmp_path / "sample_10s.mp4")
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=10:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
            "-c:v", "libx264", "-preset", "ultrafast", "-g", "30", "-c:a", "aac",
            src_video,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    out_dir = str(tmp_path / "clips")
    info = TrimSourceInfo(
        source_type="file",
        source=src_video,
        title="sample_10s",
        duration_sec=10.0,
        is_video=True,
        file_ext=".mp4",
    )

    trimmer = MediaTrimmer()
    ok, msg, out_path = trimmer.trim(
        source_info=info,
        start_sec=2.0,
        end_sec=5.0,
        output_dir=out_dir,
        audio_only=False,
        mode=TRIM_MODE_FAST,
    )
    assert ok is True, msg
    assert out_path and os.path.isfile(out_path)

    probed = probe_media_file(out_path)
    assert probed is not None
    assert 2.0 <= probed.duration_sec <= 4.5


@pytest.fixture(scope="module")
def ctk_trim_root():
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_ui_trimmer_view_and_navbar_menu(ctk_trim_root):
    selected = []
    nav = NavBar(ctk_trim_root, on_module_selected=lambda m: selected.append(m))
    nav._select_from_menu(MODULE_TRIMMER)
    assert selected == [MODULE_TRIMMER]
    assert nav.current_module == MODULE_TRIMMER

    view = TrimmerView(ctk_trim_root)
    assert view.btn_trim.cget("state") == "disabled"
    assert view.entry_start.get() == "00:00:00"

    # Simula primeiro vídeo curto (10s) com intervalo personalizado (00:00:02 -> 00:00:10)
    short_info = TrimSourceInfo(
        source_type="url",
        source="https://youtu.be/short10s",
        title="Clipe Curto",
        duration_sec=10.0,
        is_video=True,
        platform="youtube",
    )
    view._finish_analysis(short_info)
    assert view.entry_end.get() == "00:00:10"
    view.entry_start.delete(0, "end")
    view.entry_start.insert(0, "00:00:02")

    # Simula troca para segundo vídeo longo (2h14m46s) — deve resetar Início/Fim e opções 4K presentes
    mock_info = TrimSourceInfo(
        source_type="url",
        source="https://youtu.be/q4ekFpRjgKQ",
        title="Alanzoka Teste 2h",
        duration_sec=8086.0,
        is_video=True,
        platform="youtube",
    )
    view._finish_analysis(mock_info)
    assert view.btn_trim.cget("state") == "normal"
    assert "02:14:46" in view.lbl_source_info.cget("text")
    assert view.entry_start.get() == "00:00:00"
    assert view.entry_end.get() == "00:01:00"
    assert "4K (2160p)" in view.opt_quality.cget("values")
    assert not hasattr(view, "opt_mode")
