import pytest

from conftest import load_script


@pytest.fixture(scope="module")
def review():
    return load_script("review")


def base():
    return {
        "hook": {"frame0_blank": False, "first_content_s": 0.0},
        "longest_static": {"seconds": 2.0, "from_s": 1.0},
        "max_gap_between_visual_events": {"seconds": 3.0, "from_s": 1.0},
        "near_blank_frames": [], "text_density": {"longest_crowded_s": 0},
        "loudness": {"lufs": -14.2, "true_peak_dbtp": -1.5}, "dead_air": [],
        "formats": {"16x9": {"size": [1920, 1080], "duration": 60.0, "has_audio": True}},
    }


def test_clean_lesson_has_no_flags(review):
    assert review.build_flags(base(), "lesson") == []


def test_lesson_allows_a_longer_hold_than_a_short(review):
    m = base()
    m["longest_static"] = {"seconds": 4.5, "from_s": 10}
    assert review.build_flags(m, "lesson") == []
    f = review.build_flags(m, "short")
    assert f and f[0]["criterion"] == "Pacing" and f[0]["level"] == "warn"


def test_long_hold_escalates(review):
    m = base()
    m["longest_static"] = {"seconds": 11, "from_s": 3}
    f = review.build_flags(m, "lesson")
    assert f[0]["level"] == "fail" and f[0]["suggested_cap"] == 7


def test_blank_frame_zero_caps_the_hook(review):
    m = base()
    m["hook"] = {"frame0_blank": True, "first_content_s": 1.2}
    f = [x for x in review.build_flags(m, "lesson") if x["criterion"] == "Hook"]
    assert any(x["suggested_cap"] == 6 for x in f)


def test_only_mid_film_blanks_are_flagged(review):
    m = base()
    m["near_blank_frames"] = [{"where": "end", "seconds": 2.0, "from_s": 58}, {"where": "mid", "seconds": 0.6, "from_s": 20}]
    f = review.build_flags(m, "lesson")
    assert [x["metric"] for x in f] == ["near_blank_frames"] and "20" in f[0]["message"]


def test_loudness_sync_zone_and_format_flags(review):
    m = base()
    m["loudness"] = {"lufs": -20.0, "true_peak_dbtp": 0.5}
    m["sync"] = {"median_ms": 120, "mean_abs_ms": 130, "cues_with_visual": 9}
    m["safe_zone"] = {"bottom": {"longest_run_s": 2.0, "longest_run_from_s": 4.0}, "top": {"longest_run_s": 0.0, "longest_run_from_s": None}}
    m["formats"]["9x16"] = {"size": [1080, 1350], "duration": 58.0, "has_audio": False}
    metrics = {x["metric"] for x in review.build_flags(m, "lesson")}
    assert {"loudness.lufs", "loudness.true_peak_dbtp", "sync", "safe_zone.bottom", "formats.duration",
            "formats.9x16"} <= metrics
    assert "safe_zone.top" not in metrics
