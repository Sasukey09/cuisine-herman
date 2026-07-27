from app.services.video import provenance as P


def test_parse_description_timestamps_reads_mm_ss_and_hh_mm_ss():
    text = ("Au menu :\n"
            "0:00 Intro\n"
            "1:30 Recette 1 - Pâtes\n"
            "12:05 Recette 2 - Salade\n"
            "1:02:10 Recette 3 - Gâteau\n")
    ts = P.parse_description_timestamps(text)
    assert ts[0] == {"sec": 0, "label": "Intro"}
    assert ts[1] == {"sec": 90, "label": "Recette 1 - Pâtes"}
    assert ts[2]["sec"] == 725
    assert ts[3]["sec"] == 3730


def test_chapters_from_info_maps_youtube_chapters():
    info = {"chapters": [
        {"start_time": 0, "title": "Intro"},
        {"start_time": 90.0, "title": "Pâtes"},
    ]}
    assert P.chapters_from_info(info) == [
        {"start_sec": 0, "title": "Intro"},
        {"start_sec": 90, "title": "Pâtes"},
    ]


def test_video_id_of_extracts_the_id():
    assert P.video_id_of("https://www.youtube.com/watch?v=abc123DEF45") == "abc123DEF45"
    assert P.video_id_of("https://youtu.be/abc123DEF45?t=30") == "abc123DEF45"


def test_fetch_oembed_is_best_effort_and_never_raises():
    def boom(url):  # simulate network/SSRF failure
        raise RuntimeError("blocked")
    assert P.fetch_oembed("https://youtube.com/watch?v=x", fetcher=boom) == {}


def test_fetch_oembed_maps_fields():
    def ok(url):
        return {"title": "Ma vidéo", "author_name": "Chef Gad",
                "thumbnail_url": "https://img/x.jpg"}
    assert P.fetch_oembed("https://youtube.com/watch?v=x", fetcher=ok) == {
        "title": "Ma vidéo", "creator": "Chef Gad", "thumbnail": "https://img/x.jpg",
    }
