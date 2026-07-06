import shutil
import subprocess

import pytest

from conftest import load_script

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def review():
    return load_script("review")


def make_video(path, size="320x180", dur=1, audio=False):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
           f"color=c=0x203040:s={size}:r=10:d={dur}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=f=440:d={dur}", "-shortest"]
    cmd += ["-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)


def test_probe_reports_geometry_and_audio(review, tmp_path):
    p = tmp_path / "a.mp4"
    make_video(p, audio=True)
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
    make_video(tmp_path / "output" / "final.mp4", size="180x320")
    assert set(review.find_videos(str(tmp_path))) == {"9x16"}


def test_find_videos_draft_and_explicit(review, tmp_path):
    (tmp_path / "renders").mkdir()
    (tmp_path / "renders" / "draft_16x9.mp4").write_bytes(b"x")
    (tmp_path / "renders" / "16x9.mp4").write_bytes(b"x")
    assert review.find_videos(str(tmp_path), draft=True)["16x9"].endswith("draft_16x9.mp4")
    assert review.find_videos(str(tmp_path), explicit={"4x5": "z.mp4"}).keys() == {"4x5"}


def test_font_always_loads(review):
    assert review.load_font(12) is not None
