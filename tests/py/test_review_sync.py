import json

import pytest

from conftest import load_script
from synth import HAVE_FFMPEG, make_video


@pytest.fixture(scope="module")
def review():
    return load_script("review")


def test_normalize_accepts_every_shape(review):
    flat = review.normalize_cues({"s02.b": 5.0, "s01.a": 1.5, "junk": "x"})
    assert [(c["name"], c["t"]) for c in flat] == [("s01.a", 1.5), ("s02.b", 5.0)]
    nested = review.normalize_cues({"cues": {"s01.a": {"t": 2.0, "type": "pop"}}})
    assert nested == [{"name": "s01.a", "t": 2.0, "type": "pop"}]
    listed = review.normalize_cues({"cues": [{"t": 3, "type": "chime", "what": "result"}, {"nope": 1}]})
    assert listed == [{"name": "result", "t": 3.0, "type": "chime", "what": "result"}]
    pairs = review.normalize_cues([["s01.x", 4]])
    assert pairs == [{"name": "s01.x", "t": 4.0}]
    assert review.normalize_cues(None) == []


def test_load_cues_prefers_cues_json_and_degrades(review, tmp_path):
    assert review.load_cues(str(tmp_path)) == ([], None)
    (tmp_path / "grid.json").write_text(json.dumps({"cues": {"s01.start": 0.0}}))
    got, src = review.load_cues(str(tmp_path))
    assert src.endswith("grid.json") and got[0]["name"] == "s01.start"
    (tmp_path / "cues.json").write_text(json.dumps({"s01.a": 1.0}))
    assert review.load_cues(str(tmp_path))[1].endswith("cues.json")
    (tmp_path / "bad.json").write_text("{not json")
    assert review.load_cues(str(tmp_path), cues=str(tmp_path / "bad.json")) == ([], None)


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
def test_sync_offsets_measured_in_ms(review, tmp_path):
    p = tmp_path / "v.mp4"
    # slides start at 1.0 s and 3.0 s; the cues say 0.9 (picture 100 ms late) and 3.0 (on time)
    make_video(p, dur=5, fps=20, boxes=[dict(x=10, y=30, w=60, h=40, t0=1.0, dx=150, slide=0.4),
                                         dict(x=10, y=110, w=60, h=40, t0=3.0, dx=150, slide=0.4)])
    a = review.analyze(str(p))
    cues = [{"name": "late", "t": 0.9}, {"name": "ontime", "t": 3.0}, {"name": "nothing", "t": 4.6}]
    m = review.sync_metrics(cues, a["energy"], a["fps"], a["duration"])
    by = {r["cue"]: r["visual_minus_cue_ms"] for r in m["cues"]}
    assert 50 <= by["late"] <= 200
    assert abs(by["ontime"]) <= 100
    assert "nothing" not in by and m["cues_without_visual"] == 1
    assert m["worst_ms"] == by["late"] or abs(m["worst_ms"]) >= abs(by["ontime"])


def test_sync_skips_ignored_types_and_end_of_film(review):
    import numpy as np
    en = np.zeros(100)
    en[40:45] = 5
    out = review.sync_metrics([{"name": "w", "t": 2.0, "type": "whoosh"}, {"name": "z", "t": 9.99}], en, 10, 10.0)
    assert out["cues_with_visual"] == 0 and "median_ms" not in out
