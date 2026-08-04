import json
import subprocess
import sys

from conftest import SCRIPTS, SKILL


def render(*args):
    return subprocess.run(["bash", str(SCRIPTS / "render.sh"), *args],
                          capture_output=True, text=True, check=False)


def test_render_rejects_unknown_format(tmp_path):
    r = render("manim", str(tmp_path), "01", "low", "21x9")
    assert r.returncode == 2
    assert "unknown format: 21x9" in r.stderr


def test_manim_config_for_a_format():
    out = subprocess.run(
        [sys.executable, str(SKILL / "templates" / "manim" / "formats.py"), "--config", "9x16", "med"],
        capture_output=True, text=True, check=True).stdout
    cfg = dict(line.split(" = ") for line in out.splitlines() if " = " in line)
    assert out.startswith("[CLI]")
    assert (cfg["pixel_width"], cfg["pixel_height"]) == ("720", "1280")
    assert float(cfg["frame_width"]) == 8.0
    assert abs(float(cfg["frame_height"]) - 14.222222) < 1e-5
    assert cfg["frame_rate"] == "30"


def test_extract_frames_names_per_format(tmp_path):
    (tmp_path / "output").mkdir()
    r = subprocess.run(
        ["bash", str(SCRIPTS / "extract_frames.sh"), "manim", str(tmp_path), "01", "1", "9x16"],
        capture_output=True, text=True, check=False)
    assert r.returncode == 1
    assert "scene_01.9x16.mp4" in r.stderr
