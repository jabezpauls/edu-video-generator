import json
import subprocess

import pytest

from conftest import SCRIPTS

SCRIPT = SCRIPTS / "new_project.sh"


def run(base, slug):
    return subprocess.run(
        ["bash", str(SCRIPT), str(base), slug], capture_output=True, text=True, check=False
    )


def test_scaffold_layout(tmp_path):
    r = run(tmp_path, "demo")
    assert r.returncode == 0, r.stderr
    project = tmp_path / "demo"
    assert r.stdout.strip() == str(project)
    for d in (".videogen/frames", ".videogen/logs", ".videogen/critic", "scenes", "assets",
              "audio", "output"):
        assert (project / d).is_dir(), d
    assert (project / "manifest.json").is_file()
    assert (project / "storyboard.json").is_file()


def test_manifest_has_v2_state_fields(tmp_path):
    run(tmp_path, "demo")
    m = json.loads((tmp_path / "demo" / "manifest.json").read_text())
    assert m["slug"] == "demo"
    assert m["phase"] == "intake"
    assert m["engine"] is None
    assert m["mode"] == "lesson"
    assert m["formats"] == ["16x9"]
    assert m["preset"] is None
    assert m["critic_rounds"] == 0
    assert m["scores"] == {}
    assert m["render_retries"] == {}
    assert m["warnings"] == []
    assert m["created"].endswith("Z") and "T" in m["created"]


def test_storyboard_stub_carries_v2_fields(tmp_path, validator):
    run(tmp_path, "demo")
    sb = json.loads((tmp_path / "demo" / "storyboard.json").read_text())
    assert sb["mode"] == "lesson"
    assert sb["formats"] == ["16x9"]
    assert sb["preset"] is None
    # An empty stub is not a valid storyboard yet, but the only complaint is the missing scenes.
    errs = validator.manual_check(sb)
    assert errs == ["scenes must be a non-empty array"]


def test_rerun_does_not_clobber_existing_state(tmp_path):
    run(tmp_path, "demo")
    mpath = tmp_path / "demo" / "manifest.json"
    spath = tmp_path / "demo" / "storyboard.json"
    m = json.loads(mpath.read_text())
    m["phase"] = "render"
    mpath.write_text(json.dumps(m))
    spath.write_text('{"title": "mine"}')
    assert run(tmp_path, "demo").returncode == 0
    assert json.loads(mpath.read_text())["phase"] == "render"
    assert json.loads(spath.read_text()) == {"title": "mine"}


@pytest.mark.parametrize("slug", ["", "has space", "../escape", 'quo"te', "-lead", "a/b"])
def test_rejects_unsafe_slug(tmp_path, slug):
    r = run(tmp_path, slug)
    assert r.returncode != 0
    assert not (tmp_path / "escape").exists()
