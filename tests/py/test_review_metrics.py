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
    s = review.longest_static(a["chg"], a["fps"])
    assert 3.4 <= s["seconds"] <= 4.2          # 2.3 s -> 6.5 s nothing moves
    assert 2.0 <= s["from_s"] <= 2.8


def test_events_and_gap(review, clip):
    a = review.analyze(clip)
    ev = review.visual_events(a["chg"], a["fps"])
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


def test_hook_flags_blank_frame_zero(review, tmp_path):
    p = tmp_path / "h.mp4"
    make_video(p, dur=4, fps=10, boxes=[box(1.5, t1=4)])
    a = review.analyze(str(p))
    h = review.hook_metrics(a["ink"], a["std"], a["chg"], a["fps"])
    assert h["frame0_blank"] is True
    assert 1.4 <= h["first_content_s"] <= 1.9


def test_hook_good_when_content_at_frame_zero(review, tmp_path):
    p = tmp_path / "h2.mp4"
    make_video(p, dur=4, fps=10, boxes=[dict(x=20, y=40, w=100, h=60, t0=0, dx=80, slide=1.0)])
    a = review.analyze(str(p))
    h = review.hook_metrics(a["ink"], a["std"], a["chg"], a["fps"])
    assert h["frame0_blank"] is False
    assert h["first_content_s"] == 0.0
    assert h["motion_in_first_3s"] > 0.5


def test_density_flags_crowded_frames(review):
    ink = np.r_[np.full(20, 0.01), np.full(10, 0.09), np.full(20, 0.01)]
    d = review.density_metrics(ink, 10)
    assert d["crowded_seconds"] == pytest.approx(1.0)
    assert d["crowded_from_s"] == pytest.approx(2.0)
    assert d["max"] == pytest.approx(0.09)


def test_density_real_stripes_register_as_ink(review, tmp_path):
    p = tmp_path / "d.mp4"
    stripes = [dict(x=10, y=8 + i * 12, w=300, h=3, t0=0) for i in range(14)]
    make_video(p, dur=1, fps=10, boxes=stripes)
    a = review.analyze(str(p))
    assert a["ink"].mean() > 0.05


def test_slow_thin_drawing_is_not_a_static_hold(review, tmp_path):
    # a 2 px line growing slowly for 5 s moves few pixels per frame, but the picture is alive
    p = tmp_path / "slow.mp4"
    make_video(p, dur=6, fps=15, boxes=[dict(x=10, y=90, w=300, h=2, t0=0.5, dx=0, slide=0.1),
                                         dict(x=10, y=40, w=4, h=40, t0=0.5, dx=290, slide=5.0)])
    a = review.analyze(str(p))
    assert review.longest_static(a["chg"], a["fps"])["seconds"] < 1.5
