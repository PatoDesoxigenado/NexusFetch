"""Testes unitários para validação de URLs e detecção cruzada."""
import pytest
from src.config import MODULE_YOUTUBE, MODULE_INSTAGRAM, MODULE_TWITTER
from src.utils.validators import validate_url, detect_platform, ValidationStatus

def test_detect_youtube_urls():
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://m.youtube.com/watch?v=dQw4w9WgXcQ"
    ]
    for u in urls:
        assert detect_platform(u) == MODULE_YOUTUBE

def test_detect_twitter_urls():
    urls = [
        "https://twitter.com/jack/status/20",
        "https://x.com/elonmusk/status/1789000000000000000",
        "https://mobile.twitter.com/user/status/123456789"
    ]
    for u in urls:
        assert detect_platform(u) == MODULE_TWITTER

def test_detect_instagram_urls():
    urls = [
        "https://www.instagram.com/p/C-xyz123abc/",
        "https://instagram.com/reel/C-xyz123abc/",
        "https://instagr.am/reels/C-xyz123abc/"
    ]
    for u in urls:
        assert detect_platform(u) == MODULE_INSTAGRAM

def test_cross_platform_detection():
    # Estando na aba YouTube mas colando link do Twitter
    twitter_url = "https://x.com/openai/status/123456789"
    result = validate_url(twitter_url, current_module=MODULE_YOUTUBE)
    assert result.status == ValidationStatus.CROSS_MATCH
    assert result.suggested_module == MODULE_TWITTER
    assert "Twitter" in result.suggested_label

    # Estando na aba Twitter mas colando link do YouTube
    yt_url = "https://youtu.be/dQw4w9WgXcQ"
    result2 = validate_url(yt_url, current_module=MODULE_TWITTER)
    assert result2.status == ValidationStatus.CROSS_MATCH
    assert result2.suggested_module == MODULE_YOUTUBE

def test_invalid_url():
    result = validate_url("https://www.google.com/search?q=nexus", current_module=MODULE_YOUTUBE)
    assert result.status == ValidationStatus.INVALID
