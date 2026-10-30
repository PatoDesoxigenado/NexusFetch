"""Testes funcionais e unitários para metadata e downloader."""
import pytest
from src.core.metadata import extract_media_info, MediaMetadata
from src.core.downloader import MediaDownloader
from src.utils.helpers import format_bytes, format_duration, sanitize_filename

def test_helpers_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"

def test_helpers_format_duration():
    assert format_duration(0) == "00:00"
    assert format_duration(65) == "01:05"
    assert format_duration(3665) == "01:01:05"

def test_helpers_sanitize_filename():
    assert sanitize_filename("Video: Top 10 / Best * Ever?") == "Video_ Top 10 _ Best _ Ever_"
    assert sanitize_filename("   ...clean...   ") == "clean"

def test_extract_invalid_media():
    meta = extract_media_info("https://www.youtube.com/watch?v=invalid_id_9999999")
    assert meta.error is not None
    assert "Erro" in meta.title or meta.error != ""

def test_downloader_init_and_cancel():
    downloader = MediaDownloader()
    assert downloader._is_cancelled is False
    downloader.cancel()
    assert downloader._is_cancelled is True

def test_extract_twitter_photo():
    meta = extract_media_info("https://x.com/clarionrox/status/2115745833500942413")
    assert meta.error is None
    assert meta.media_type == "image"
    assert "Clarion" in meta.uploader
    assert len(meta.image_urls) > 0
    assert len(meta.qualities) > 0
    assert "Imagem Original" in meta.qualities[0].label

def test_extract_instagram_photo():
    meta = extract_media_info("https://www.instagram.com/p/De7_PCUOija/")
    assert meta.error is None
    assert meta.media_type == "image"
    assert len(meta.image_urls) > 0
    assert meta.thumbnail_url is not None
    assert "kel" in meta.uploader
    assert len(meta.qualities) > 0

def test_playlist_metadata_structure():
    from src.core.metadata import PlaylistItem
    item1 = PlaylistItem(
        index=1,
        video_id="abc1",
        title="Aula 1 - Intro",
        duration=120,
        duration_str="02:00",
        url="https://www.youtube.com/watch?v=abc1",
        thumbnail_url="https://i.ytimg.com/vi/abc1/hqdefault.jpg",
        is_selected=True
    )
    item2 = PlaylistItem(
        index=2,
        video_id="abc2",
        title="Aula 2 - Prática",
        duration=240,
        duration_str="04:00",
        url="https://www.youtube.com/watch?v=abc2",
        thumbnail_url="https://i.ytimg.com/vi/abc2/hqdefault.jpg",
        is_selected=False
    )
    pl_meta = MediaMetadata(
        url="https://www.youtube.com/playlist?list=PLtest",
        title="Curso Completo",
        uploader="Professor X",
        duration=360,
        duration_str="2 vídeos",
        thumbnail_url="https://i.ytimg.com/vi/abc1/hqdefault.jpg",
        media_type="playlist",
        is_playlist=True,
        playlist_items=[item1, item2],
        playlist_count=2
    )

    assert pl_meta.is_playlist is True
    assert pl_meta.media_type == "playlist"
    assert pl_meta.playlist_count == 2
    selected = [it for it in pl_meta.playlist_items if it.is_selected]
    assert len(selected) == 1
    assert selected[0].title == "Aula 1 - Intro"

def test_downloader_playlist_empty_selection(tmp_path):
    downloader = MediaDownloader()
    completed = []
    
    downloader._run_download(
        url="https://www.youtube.com/playlist?list=PLtest",
        output_dir=str(tmp_path),
        mode="video",
        format_id="best",
        media_type="playlist",
        image_urls=None,
        title="Playlist Teste",
        playlist_items=[],  # Nenhum item selecionado
        on_progress=None,
        on_status=None,
        on_complete=lambda ok, msg, path: completed.append((ok, msg))
    )

    assert len(completed) == 1
    assert completed[0][0] is False
    assert "Nenhum vídeo" in completed[0][1]


