"""Bug 4 regression: broaden YouTube caption coverage so yt-dlp (blocked from
datacenter IPs) is a last resort, and honour a cookies file when present."""
import sys
import types

from app.services.video import transcript as tx
from app.services.video import audio


class _FakeTranscript:
    def __init__(self, text, translatable=False, lang="es"):
        self._text = text
        self.is_translatable = translatable
        self.language_code = lang

    def translate(self, lang):
        return _FakeTranscript(self._text + f"[->{lang}]", False, lang)

    def fetch(self):
        return [{"text": self._text}]


class _FakeList:
    def __init__(self, manual=None, generated=None, any_t=None):
        self._manual, self._generated, self._any = manual, generated, any_t

    def find_manually_created_transcript(self, langs):
        if self._manual:
            return self._manual
        raise Exception("no manual transcript")

    def find_generated_transcript(self, langs):
        if self._generated:
            return self._generated
        raise Exception("no generated transcript")

    def __iter__(self):
        return iter([self._any] if self._any else [])


def _install_fake(monkeypatch, tlist):
    api = types.SimpleNamespace(
        list_transcripts=lambda vid: tlist,
        get_transcript=lambda vid, languages=None: [{"text": "legacy"}],
    )
    mod = types.ModuleType("youtube_transcript_api")
    mod.YouTubeTranscriptApi = api
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", mod)


def test_captions_prefers_manual(monkeypatch):
    _install_fake(monkeypatch, _FakeList(manual=_FakeTranscript("recette manuelle")))
    assert tx._youtube_captions("vid") == "recette manuelle"


def test_captions_fall_back_to_generated(monkeypatch):
    _install_fake(monkeypatch, _FakeList(generated=_FakeTranscript("recette auto")))
    assert tx._youtube_captions("vid") == "recette auto"


def test_captions_translate_any_language(monkeypatch):
    # Only a Spanish track exists -> translate it to the first preferred lang (fr).
    _install_fake(monkeypatch, _FakeList(any_t=_FakeTranscript("receta", translatable=True, lang="es")))
    out = tx._youtube_captions("vid")
    assert out and "[->fr]" in out


def test_captions_none_when_no_transcripts(monkeypatch):
    _install_fake(monkeypatch, _FakeList())
    assert tx._youtube_captions("vid") is None


# --------------------------------------------------------------------------- #
# The actual bug this closes: youtube-transcript-api 1.0 REMOVED the static
# list_transcripts/get_transcript and replaced them with an *instance* .list().
# The code only called the old ones, so an unpinned bump broke every caption
# fetch (AttributeError -> None -> falls to blocked yt-dlp). We now support both.
# --------------------------------------------------------------------------- #
def _install_fake_new(monkeypatch, tlist, capture=None):
    class _Api:  # 1.x: instantiate, then .list(); NO static list_transcripts
        def __init__(self, proxy_config=None):
            if capture is not None:
                capture["proxy"] = proxy_config

        def list(self, vid):
            return tlist

    mod = types.ModuleType("youtube_transcript_api")
    mod.YouTubeTranscriptApi = _Api
    proxies = types.ModuleType("youtube_transcript_api.proxies")

    class WebshareProxyConfig:
        def __init__(self, proxy_username=None, proxy_password=None):
            self.kind = "webshare"

    class GenericProxyConfig:
        def __init__(self, http_url=None, https_url=None):
            self.kind = "generic"

    proxies.WebshareProxyConfig = WebshareProxyConfig
    proxies.GenericProxyConfig = GenericProxyConfig
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", mod)
    monkeypatch.setitem(sys.modules, "youtube_transcript_api.proxies", proxies)


def test_captions_work_with_the_new_1x_instance_api(monkeypatch):
    _install_fake_new(monkeypatch, _FakeList(manual=_FakeTranscript("recette 1x")))
    assert tx._youtube_captions("vid") == "recette 1x"


def test_new_api_receives_the_configured_proxy(monkeypatch):
    cap = {}
    _install_fake_new(monkeypatch, _FakeList(manual=_FakeTranscript("x")), capture=cap)
    monkeypatch.delenv("WEBSHARE_PROXY_USERNAME", raising=False)
    monkeypatch.setenv("YOUTUBE_HTTPS_PROXY", "http://proxy.example:8080")
    tx._youtube_captions("vid")
    assert cap.get("proxy") is not None, "the proxy must be handed to the API when configured"


def test_proxy_config_prefers_webshare(monkeypatch):
    _install_fake_new(monkeypatch, _FakeList())
    monkeypatch.setenv("WEBSHARE_PROXY_USERNAME", "u")
    monkeypatch.setenv("WEBSHARE_PROXY_PASSWORD", "p")
    pc = tx._proxy_config()
    assert getattr(pc, "kind", None) == "webshare"


def test_base_opts_uses_cookiefile_when_present(monkeypatch, tmp_path):
    ck = tmp_path / "cookies.txt"
    ck.write_text("# Netscape HTTP Cookie File")
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(ck))
    assert audio._base_opts().get("cookiefile") == str(ck)


def test_base_opts_no_cookiefile_when_absent(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    assert "cookiefile" not in audio._base_opts()
    # anti-bot mitigations still present
    assert "ios" in audio._base_opts()["extractor_args"]["youtube"]["player_client"]


# --------------------------------------------------------------------------- #
# Client-provided transcript path: the mobile app fetches captions from the
# phone's residential IP (not blocked) and posts the text; the server runs only
# the AI extraction, never a YouTube fetch (no datacenter-IP block, no SSRF).
# --------------------------------------------------------------------------- #
def test_extract_from_transcript_runs_ai_without_any_fetch():
    from app.services.video import service as svc

    class FakeExtractor:
        def extract(self, text, hint_title=None):
            return {"name": "Tarte", "hint": hint_title, "seen": text[:15]}

    class FakeDB:
        def add(self, *a):
            pass

        def commit(self):
            pass

    out = svc.extract_recipe_from_transcript(
        FakeDB(), "t1", "Prenez 3 pommes, du beurre et du sucre.",
        url="https://youtu.be/abc", title="Ma tarte", extractor=FakeExtractor(),
    )
    assert out["platform"] == "youtube_client"
    assert out["transcript_source"] == "client_captions"
    assert out["draft"]["name"] == "Tarte"
    assert out["draft"]["hint"] == "Ma tarte"


def test_extract_from_transcript_rejects_empty():
    import pytest
    from app.services.video import service as svc
    from app.services.video.errors import TranscriptUnavailableError

    class FakeDB:
        def add(self, *a):
            pass

        def commit(self):
            pass

    with pytest.raises(TranscriptUnavailableError):
        svc.extract_recipe_from_transcript(FakeDB(), "t1", "   ")
