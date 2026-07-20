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
