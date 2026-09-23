import pytest

from conftest import load_script
from synth import HAVE_FFMPEG, make_video

pytestmark = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def review():
    return load_script("review")


def test_probe_reports_geometry_and_audio(review, tmp_path):
    p = tmp_path / "a.mp4"
    make_video(p, dur=1, tones=[(0, 1, 440, 0.3)])
    w, h, fps, dur, audio = review.probe(str(p))
    assert (w, h) == (320, 180)
    assert fps == pytest.approx(10)
    assert dur == pytest.approx(1, abs=0.2)
    assert audio


def test_format_of_by_aspect(review):
    assert review.format_of(1920, 1080) == "16x9"
    assert review.format_of(1080, 1920) == "9x16"
    assert review.format_of(1080, 1350) == "4x5"
    assert review.format_of(1000, 1000) == "1x1"


def test_find_videos_engine_layouts(review, tmp_path):
    (tmp_path / "renders").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "renders" / "9x16.mp4").write_bytes(b"x")
    (tmp_path / "output" / "final_16x9.mp4").write_bytes(b"x")
    found = review.find_videos(str(tmp_path))
    assert set(found) == {"9x16", "16x9"}


def test_find_videos_lone_final_is_named_by_aspect(review, tmp_path):
    (tmp_path / "output").mkdir()
    make_video(tmp_path / "output" / "final.mp4", size="180x320", dur=1)
    assert set(review.find_videos(str(tmp_path))) == {"9x16"}


def test_find_videos_draft_and_explicit(review, tmp_path):
    (tmp_path / "renders").mkdir()
    (tmp_path / "renders" / "draft_16x9.mp4").write_bytes(b"x")
    (tmp_path / "renders" / "16x9.mp4").write_bytes(b"x")
    assert review.find_videos(str(tmp_path), draft=True)["16x9"].endswith("draft_16x9.mp4")
    assert review.find_videos(str(tmp_path), explicit={"4x5": "z.mp4"}).keys() == {"4x5"}


def test_font_always_loads(review):
    assert review.load_font(12) is not None


def test_analyze_streams_per_frame_arrays(review, tmp_path):
    p = tmp_path / "m.mp4"
    make_video(p, fps=15, boxes=[dict(x=10, y=60, w=60, h=60, t0=0.2, dx=200, slide=1.0)])
    a = review.analyze(str(p))
    assert a["fps"] == pytest.approx(15)
    assert len(a["energy"]) == len(a["std"]) - 1
    assert 28 <= len(a["std"]) <= 31
    assert a["energy"].mean() > 0.3
    assert a["ink"].max() > 0.005


def test_find_videos_primary_final_joins_the_suffixed_formats(review, tmp_path):
    """Manim/Remotion/motion finals: final.mp4 is the primary format, final_<fmt>.mp4 the others."""
    (tmp_path / "output").mkdir()
    make_video(tmp_path / "output" / "final.mp4", size="320x180", dur=1)
    make_video(tmp_path / "output" / "final_9x16.mp4", size="180x320", dur=1)
    found = review.find_videos(str(tmp_path))
    assert set(found) == {"16x9", "9x16"}
    assert found["16x9"].endswith("final.mp4") and found["9x16"].endswith("final_9x16.mp4")
