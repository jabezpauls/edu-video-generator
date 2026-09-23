import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS
from synth import HAVE_FFMPEG, make_video

pytestmark = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")


def review_cli(project, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / "review.py"), "1", "--project", str(project), *args],
                          capture_output=True, text=True, check=False)


@pytest.fixture
def project(tmp_path):
    """A two-format lesson: 16x9 and 9x16, narration tone, a hold in the middle."""
    (tmp_path / "renders").mkdir()
    tones = [(0, 3, 440, 0.25), (4, 7, 440, 0.25)]
    make_video(tmp_path / "renders" / "16x9.mp4", size="320x180", fps=10, dur=8, tones=tones,
               boxes=[dict(x=10, y=30, w=60, h=40, t0=0.0, dx=150, slide=0.4),
                      dict(x=10, y=100, w=60, h=40, t0=7.0, dx=150, slide=0.4)])
    make_video(tmp_path / "renders" / "9x16.mp4", size="180x320", fps=10, dur=8, tones=tones,
               boxes=[dict(x=10, y=100, w=60, h=40, t0=0.0, dx=90, slide=0.4),
                      dict(x=10, y=290, w=160, h=14, t0=2.0, t1=5.0)])
    (tmp_path / "storyboard.json").write_text(json.dumps({"mode": "lesson", "formats": ["16x9", "9x16"]}))
    return tmp_path


def test_review_writes_the_full_kit(project):
    r = review_cli(project)
    assert r.returncode == 0, r.stderr
    out = project / "review" / "r1"
    names = {p.name for p in out.iterdir()}
    assert {"contact.jpg", "strip_fast.jpg", "phone_16x9.jpg", "phone_9x16.jpg", "safe_9x16.jpg",
            "metrics.json"} <= names
    m = json.loads((out / "metrics.json").read_text())
    assert m["primary_format"] == "16x9" and m["mode"] == "lesson"
    assert set(m["formats"]) == {"16x9", "9x16"}
    assert m["longest_static"]["seconds"] > 5            # held from ~0.5 s to 7 s
    assert m["safe_zone"]["bottom"]["longest_run_s"] > 1.5
    assert any(f["metric"] == "safe_zone.bottom" for f in m["flags"])
    assert m["sync"] is None and "sync_note" in m          # no cue file: degrades, does not crash
    assert m["loudness"]["lufs"] < 0


def test_review_scores_cue_sync_when_a_grid_exists(project):
    (project / "cues.json").write_text(json.dumps({"s01.a": 0.0, "s02.b": 7.0, "s01.nothing": 4.0}))
    assert review_cli(project).returncode == 0
    m = json.loads((project / "review" / "r1" / "metrics.json").read_text())
    assert m["sync"]["source"] == "cues.json"
    assert m["sync"]["cues_with_visual"] >= 2


def test_review_without_renders_fails_politely(tmp_path):
    r = review_cli(tmp_path)
    assert r.returncode != 0 and "no renders found" in (r.stderr + r.stdout)


def test_explicit_video_flag_for_any_engine_layout(tmp_path):
    make_video(tmp_path / "scene.mp4", size="320x180", fps=10, dur=3, tones=[(0, 3, 440, 0.2)],
               boxes=[dict(x=10, y=30, w=60, h=40, t0=0.5, dx=100)])
    r = review_cli(tmp_path, "--video", f"16x9={tmp_path / 'scene.mp4'}", "--mode", "short")
    assert r.returncode == 0, r.stderr
    m = json.loads((tmp_path / "review" / "r1" / "metrics.json").read_text())
    assert m["mode"] == "short" and set(m["formats"]) == {"16x9"}


def test_project_can_be_given_as_the_second_argument_like_the_other_scripts(project):
    r = subprocess.run([sys.executable, str(SCRIPTS / "review.py"), "2", str(project)],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert (project / "review" / "r2" / "metrics.json").is_file()
