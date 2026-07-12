import numpy as np
import pytest

from conftest import load_script
from synth import HAVE_FFMPEG, make_video

pytestmark = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def review():
    return load_script("review")


def box(t0, y=40, dx=120, **kw):
    return dict(x=20, y=y, w=60, h=40, t0=t0, dx=dx, slide=0.3, **kw)


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    """8 s at 10 fps: blank 0-1 s, slide at 1 s, slide at 2 s, still until a slide at 6.5 s,
    then everything vanishes into a blank hold at 7.5 s."""
    p = tmp_path_factory.mktemp("c") / "clip.mp4"
    make_video(p, dur=8, fps=10, boxes=[
        box(1.0, y=20, t1=7.5), box(2.0, y=80, t1=7.5), box(6.5, y=130, t1=7.5)])
    return str(p)


def test_longest_static_run(review, clip):
    a = review.analyze(clip)
    s = review.longest_static(a["energy"], a["fps"])
    assert 3.4 <= s["seconds"] <= 4.2          # 2.3 s -> 6.5 s nothing moves
    assert 2.0 <= s["from_s"] <= 2.8


def test_events_and_gap(review, clip):
    a = review.analyze(clip)
    ev = review.visual_events(a["energy"], a["fps"])
    assert any(abs(t - 1.0) < 0.35 for t in ev)
    assert any(abs(t - 2.0) < 0.35 for t in ev)
    assert any(abs(t - 6.5) < 0.35 for t in ev)
    gap = review.max_gap(ev, a["duration"])
    assert 3.4 <= gap["seconds"] <= 4.8
    assert gap["from_s"] == pytest.approx(2.0, abs=0.7)


def test_blank_runs_classified(review, tmp_path):
    p = tmp_path / "b.mp4"
    # content from 1 s to 3 s only: blank at start and blank at end
    make_video(p, dur=4, fps=10, boxes=[dict(x=0, y=0, w=320, h=90, color="white", t0=1, t1=3)])
    a = review.analyze(str(p))
    runs = review.blank_runs(a["std"], a["mean"], a["fps"])
    assert [r["where"] for r in runs] == ["start", "end"]
    assert runs[0]["seconds"] == pytest.approx(1.0, abs=0.2)


def test_no_blank_runs_on_busy_clip(review, clip):
    a = review.analyze(clip)
    runs = review.blank_runs(a["std"], a["mean"], a["fps"])
    assert [r["where"] for r in runs if r["where"] == "mid"] == []
