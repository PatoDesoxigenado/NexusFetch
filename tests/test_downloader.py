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


