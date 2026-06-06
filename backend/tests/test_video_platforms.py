import pytest

from app.services.video.platforms import (
    detect_platform,
    is_youtube,
    youtube_video_id,
)
from app.services.video.errors import UnsupportedURLError


def test_detect_platforms():
    assert detect_platform("https://www.youtube.com/watch?v=abc123XYZ_1") == "youtube"
    assert detect_platform("https://youtu.be/abc123XYZ_1") == "youtube"
    assert detect_platform("https://www.tiktok.com/@chef/video/123") == "tiktok"
    assert detect_platform("https://www.instagram.com/reel/abc/") == "instagram"
    assert detect_platform("https://fb.watch/xyz/") == "facebook"
    assert detect_platform("https://vimeo.com/12345") == "vimeo"
    assert detect_platform("https://example.com/some/video") == "other"


def test_detect_rejects_non_http():
    with pytest.raises(UnsupportedURLError):
        detect_platform("ftp://foo/bar")
    with pytest.raises(UnsupportedURLError):
        detect_platform("not a url")


def test_is_youtube():
    assert is_youtube("https://m.youtube.com/watch?v=zzzzzzzzzzz") is True
    assert is_youtube("https://www.tiktok.com/@x/video/1") is False


def test_youtube_video_id_shapes():
    assert youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_video_id("https://www.youtube.com/shorts/abc123def45") == "abc123def45"
    assert youtube_video_id("https://www.youtube.com/embed/abc123def45") == "abc123def45"
    assert youtube_video_id("https://www.tiktok.com/@x/video/1") is None
