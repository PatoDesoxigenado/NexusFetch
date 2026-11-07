"""Testes unitários e de integração para o conversor de mídia (MediaConverter)."""
import os
import shutil
import tempfile
import subprocess
import pytest

from src.core.converter import (
    MediaConverter,
    MediaFileInfo,
    probe_media_file,
    build_conversion_args,
    get_ffmpeg_executable,
)

@pytest.fixture(scope="module")
def sample_media_files():
    """Gera arquivos de teste sintetizados ultrarrápidos (1 segundo) via FFmpeg."""
    tmp_dir = tempfile.mkdtemp(prefix="nexus_converter_test_")
    ffmpeg_cmd = get_ffmpeg_executable()

    video_mp4 = os.path.join(tmp_dir, "test_sample.mp4")
    audio_mp3 = os.path.join(tmp_dir, "test_sample.mp3")

    # Gera 1s de vídeo MP4 sintético com áudio
    cmd_video = [
        ffmpeg_cmd, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=15",
        "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k",
        video_mp4
    ]
    subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Gera 1s de áudio MP3 sintético
    cmd_audio = [
        ffmpeg_cmd, "-y",
        "-f", "lavfi", "-i", "sine=duration=1:frequency=440",
        "-c:a", "libmp3lame", "-b:a", "128k",
        audio_mp3
    ]
    subprocess.run(cmd_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    yield {
        "dir": tmp_dir,
        "video_mp4": video_mp4,
        "audio_mp3": audio_mp3
    }

    shutil.rmtree(tmp_dir, ignore_errors=True)

def test_probe_non_existent():
    res = probe_media_file("arquivo_que_nao_existe_123.mp4")
    assert res is None

def test_probe_media_file(sample_media_files):
    v_path = sample_media_files["video_mp4"]
    info = probe_media_file(v_path)
    assert info is not None
    assert info.is_video is True
    assert info.ext == ".mp4"
    assert info.size_bytes > 0
    assert info.duration_sec >= 0.8
    assert info.width == 320
    assert info.height == 240

    a_path = sample_media_files["audio_mp3"]
    a_info = probe_media_file(a_path)
    assert a_info is not None
    assert a_info.is_audio is True
    assert a_info.ext == ".mp3"
    assert a_info.duration_sec >= 0.8

def test_build_args_mp4_to_mp4_codecs():
    # H.264
    args_h264 = build_conversion_args("in.mp4", "out.mp4", "MP4", resolution_key="original", codec_key="h264")
    assert any(enc in args_h264 for enc in ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"])
    assert "+faststart" in args_h264
    assert "-progress" in args_h264

    # HEVC
    args_hevc = build_conversion_args("in.mp4", "out.mp4", "MP4", resolution_key="original", codec_key="hevc")
    assert any(enc in args_hevc for enc in ["hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265"])

    # AV1
    args_av1 = build_conversion_args("in.mp4", "out.mp4", "MP4", resolution_key="original", codec_key="av1")
    assert any(enc in args_av1 for enc in ["av1_nvenc", "av1_qsv", "av1_amf", "libaom-av1"])

    # VP9
    args_vp9 = build_conversion_args("in.mp4", "out.mp4", "MP4", resolution_key="original", codec_key="vp9")
    assert "libvpx-vp9" in args_vp9

def test_build_args_resolutions():
    # 1080p
    args_1080 = build_conversion_args("in.mp4", "out.mp4", "MP4", resolution_key="1080p")
    assert "-vf" in args_1080
    assert "scale=-2:1080" in args_1080

    # 720p
    args_720 = build_conversion_args("in.mp4", "out.mp4", "MP4", resolution_key="720p")
    assert "scale=-2:720" in args_720

    # 4K
    args_4k = build_conversion_args("in.mp4", "out.mp4", "MP4", resolution_key="2160p")
    assert "scale=-2:2160" in args_4k

def test_build_args_other_video_formats():
    # MKV
    args_mkv = build_conversion_args("in.mp4", "out.mkv", "MKV", resolution_key="original")
    assert "out.mkv" in args_mkv
    assert any(enc in args_mkv for enc in ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"])

    # AVI
    args_avi = build_conversion_args("in.mp4", "out.avi", "AVI", resolution_key="original")
    assert "out.avi" in args_avi
    assert "mpeg4" in args_avi

    # WEBM
    args_webm = build_conversion_args("in.mp4", "out.webm", "WEBM", resolution_key="original")
    assert "out.webm" in args_webm
    assert "libvpx-vp9" in args_webm

def test_build_args_audio_extraction_and_conversion():
    # MP4 para MP3 320k
    args_mp3 = build_conversion_args("in.mp4", "out.mp3", "MP3", resolution_key="original")
    assert "-vn" in args_mp3
    assert "libmp3lame" in args_mp3
    assert "320k" in args_mp3

    # MP3 para WAV
    args_wav = build_conversion_args("in.mp3", "out.wav", "WAV")
    assert "-vn" in args_wav
    assert "pcm_s16le" in args_wav

    # MP3 para FLAC
    args_flac = build_conversion_args("in.mp3", "out.flac", "FLAC")
    assert "-vn" in args_flac
    assert "flac" in args_flac

    # MP3 para M4A
    args_m4a = build_conversion_args("in.mp3", "out.m4a", "M4A")
    assert "-vn" in args_m4a
    assert "aac" in args_m4a
    assert "320k" in args_m4a

def test_real_conversion_batch(sample_media_files):
    v_path = sample_media_files["video_mp4"]
    a_path = sample_media_files["audio_mp3"]
    out_dir = os.path.join(sample_media_files["dir"], "output")

    v_info = probe_media_file(v_path)
    a_info = probe_media_file(a_path)
    assert v_info is not None and a_info is not None

    converter = MediaConverter()

    # 1. Converte MP4 para MP4 480p
    success, total, errors = converter.convert_batch(
        files=[v_info],
        output_dir=out_dir,
        target_format="MP4",
        resolution_key="480p",
        codec_key="h264"
    )
    assert success == 1
    assert total == 1
    assert len(errors) == 0

    converted_file = os.path.join(out_dir, "test_sample.mp4")
    assert os.path.exists(converted_file)
    assert os.path.getsize(converted_file) > 0

    # 1.1 Se o destino for a MESMA pasta do original, adiciona sufixo _converted para não sobrescrever
    same_dir = os.path.dirname(v_path)
    success_same, _, _ = converter.convert_batch(
        files=[v_info],
        output_dir=same_dir,
        target_format="MP4",
        resolution_key="480p",
        codec_key="h264"
    )
    assert success_same == 1
    same_dir_file = os.path.join(same_dir, "test_sample_converted.mp4")
    assert os.path.exists(same_dir_file)
    assert os.path.getsize(same_dir_file) > 0

    # 2. Converte MP4 para MP3 320k
    success_mp3, _, _ = converter.convert_batch(
        files=[v_info],
        output_dir=out_dir,
        target_format="MP3",
    )
    assert success_mp3 == 1
    mp3_file = os.path.join(out_dir, "test_sample.mp3")
    assert os.path.exists(mp3_file)
    assert os.path.getsize(mp3_file) > 0
