"""Testes unitários para detecção, deduplicação e download seletivo de carrosséis (Instagram / Twitter)."""
import os
import time
from unittest.mock import patch
from src.core.metadata import (
    _deduplicate_media_urls,
    _build_carousel_metadata,
    _upgrade_twitter_image_url_to_orig,
)
from src.core.downloader import MediaDownloader


def test_deduplicate_media_urls_removes_query_variants():
    raw = [
        "https://scontent.cdninstagram.com/v/t51/111_n.jpg?stp=dst-jpg&_nc_cat=100",
        "https://scontent.cdninstagram.com/v/t51/111_n.jpg?stp=dst-jpg&_nc_cat=100&dl=1",
        "https://scontent.cdninstagram.com/v/t51/222_n.jpg?stp=dst-jpg",
        "https://scontent.cdninstagram.com/v/t51/222_n.jpg?dl=1",
        "https://scontent.cdninstagram.com/v/t51/333_n.mp4?efg=abc",
    ]
    deduped = _deduplicate_media_urls(raw)
    assert len(deduped) == 3
    assert "111_n.jpg" in deduped[0]
    assert "222_n.jpg" in deduped[1]
    assert "333_n.mp4" in deduped[2]


def test_build_carousel_metadata_mixed_media():
    urls = [
        "https://cdn.example.com/a/slide1.jpg?size=orig",
        "https://cdn.example.com/a/slide2.mp4?tag=1",
        "https://cdn.example.com/a/slide3.png",
    ]
    meta = _build_carousel_metadata(
        url="https://www.instagram.com/p/Test123/",
        title="Post Teste",
        uploader="Autor",
        media_urls=urls,
        thumbnail_url=urls[0],
    )
    assert meta.media_type == "carousel"
    assert meta.is_playlist is True
    assert meta.playlist_count == 3
    assert len(meta.playlist_items) == 3
    assert meta.playlist_items[0].item_type == "image"
    assert meta.playlist_items[1].item_type == "video"
    assert meta.playlist_items[2].item_type == "image"
    assert len(meta.image_urls) == 2


def test_downloader_carousel_downloads_only_selected_and_no_false_concluido(tmp_path):
    urls = [
        "https://cdn.example.com/p/photo1.jpg",
        "https://cdn.example.com/p/photo2.mp4",
        "https://cdn.example.com/p/photo3.jpg",
    ]
    meta = _build_carousel_metadata(
        url="https://www.instagram.com/p/Test123/",
        title="Carrossel Teste",
        uploader="Autor",
        media_urls=urls,
        thumbnail_url=urls[0],
    )
    # Desmarca o segundo item
    meta.playlist_items[1].is_selected = False

    progress_calls = []
    completed = []

    dl = MediaDownloader()
    with patch.object(MediaDownloader, "_download_direct_media_bytes", return_value=b"FAKE_MEDIA"):
        dl.download_async(
            url=meta.url,
            output_dir=str(tmp_path),
            mode="image",
            media_type="carousel",
            title=meta.title,
            playlist_items=meta.playlist_items,
            on_progress=lambda pct, spd, eta, fname: progress_calls.append((pct, spd, eta, fname)),
            on_complete=lambda ok, msg, path: completed.append((ok, msg, path)),
        )
        dl._current_thread.join(timeout=5)

    assert len(completed) == 1
    assert completed[0][0] is True
    assert "2 de 2" in completed[0][1]

    saved_files = sorted(os.listdir(tmp_path))
    assert saved_files == ["Carrossel Teste_01.jpg", "Carrossel Teste_03.jpg"]

    # Garante que nunca exibiu "Concluído" ou "00:00" durante o progresso
    for pct, spd, eta, _ in progress_calls:
        assert "Concluído" not in spd
        assert eta != "00:00"


def test_downloader_multi_image_progress_does_not_show_concluido_early(tmp_path):
    urls = [
        "https://cdn.example.com/1.jpg",
        "https://cdn.example.com/2.jpg",
        "https://cdn.example.com/3.jpg",
    ]
    progress_calls = []
    completed = []

    dl = MediaDownloader()
    with patch.object(MediaDownloader, "_download_direct_media_bytes", return_value=b"IMG"):
        dl.download_async(
            url=urls[0],
            output_dir=str(tmp_path),
            mode="image",
            media_type="image",
            image_urls=urls,
            title="Multi",
            on_progress=lambda pct, spd, eta, fname: progress_calls.append((pct, spd, eta, fname)),
            on_complete=lambda ok, msg, path: completed.append((ok, msg, path)),
        )
        dl._current_thread.join(timeout=5)

    assert completed[0][0] is True
    assert len(progress_calls) == 3
    for _, spd, eta, _ in progress_calls:
        assert "Concluído" not in spd
        assert eta != "00:00"


def test_upgrade_twitter_image_url_to_orig():
    assert _upgrade_twitter_image_url_to_orig(
        "https://pbs.twimg.com/media/HXNNyC7XoAAK9Hn.jpg"
    ) == "https://pbs.twimg.com/media/HXNNyC7XoAAK9Hn.jpg?name=orig"

    assert _upgrade_twitter_image_url_to_orig(
        "https://pbs.twimg.com/media/HXNNyC7XoAAK9Hn?format=jpg&name=large"
    ) == "https://pbs.twimg.com/media/HXNNyC7XoAAK9Hn?format=jpg&name=orig"

    # Não altera URLs que não são pbs.twimg.com/media
    other = "https://scontent.cdninstagram.com/v/photo.jpg?stp=dst-jpg"
    assert _upgrade_twitter_image_url_to_orig(other) == other
