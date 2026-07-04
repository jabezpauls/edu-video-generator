import json
import shutil
import subprocess

import pytest

from conftest import SCRIPTS


@pytest.fixture
def quirky_project(tmp_path, v1_storyboard):
    """A project whose path contains a quote, which used to break inline python."""
    p = tmp_path / "it's a project"
    p.mkdir()
    (p / "storyboard.json").write_text(json.dumps(v1_storyboard))
    return p


def test_render_all_reads_scene_ids_from_odd_paths(quirky_project):
    # An unknown engine is rejected once per scene id; if ids were never read, it would exit 0.
    r = subprocess.run(
        ["bash", str(SCRIPTS / "render.sh"), "bogus", str(quirky_project), "all"],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 2
    assert "unknown engine: bogus" in r.stderr


def test_render_rejects_unknown_engine_for_single_scene(quirky_project):
    r = subprocess.run(
        ["bash", str(SCRIPTS / "render.sh"), "bogus", str(quirky_project), "01"],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 2


def test_extract_frames_rejects_unknown_engine(tmp_path):
    r = subprocess.run(
        ["bash", str(SCRIPTS / "extract_frames.sh"), "bogus", str(tmp_path), "01", "1"],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 2


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_mux_without_scene_videos_reports_missing(quirky_project):
    r = subprocess.run(
        ["bash", str(SCRIPTS / "mux.sh"), str(quirky_project)],
        capture_output=True, text=True, check=False,
    )
    assert "missing scene video" in r.stderr
    assert "scene_01.mp4" in r.stderr


@pytest.mark.parametrize("script", sorted(p.name for p in SCRIPTS.glob("*.sh")))
def test_shell_scripts_parse(script):
    r = subprocess.run(["bash", "-n", str(SCRIPTS / script)], capture_output=True, text=True,
                       check=False)
    assert r.returncode == 0, r.stderr
