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


def test_motion_engine_scaffold(tmp_path):
    r = subprocess.run(["bash", str(SCRIPT), str(tmp_path), "demo", "motion"],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    project = tmp_path / "demo"
    assert r.stdout.strip() == str(project)
    for f in ("film/index.html", "film/core.js", "film/type.js", "film/film.js", "film/data.js",
              "film/lib/motion.js", "film/lib/time.js", "timeline.json", "cues.json",
              "package.json"):
        assert (project / f).is_file(), f
    assert json.loads((project / "manifest.json").read_text())["engine"] == "motion"
    assert json.loads((project / "storyboard.json").read_text())["engine"] == "motion"
    assert "playwright" in json.loads((project / "package.json").read_text())["devDependencies"]


def test_motion_scaffold_has_every_file_the_page_loads(tmp_path):
    import re
    subprocess.run(["bash", str(SCRIPT), str(tmp_path), "demo", "motion"], check=True, capture_output=True)
    film = tmp_path / "demo" / "film"
    page = (film / "index.html").read_text()
    refs = re.findall(r'(?:src|href)="([^"]+)"', page)
    assert any(r.startswith("edu/") for r in refs) and any("katex" in r for r in refs)
    missing = [r for r in refs if not (film / r).is_file()]
    assert not missing, missing
    # the KaTeX stylesheet points at fonts that were copied too
    css = (film / "vendor/katex/katex.min.css").read_text()
    fonts = set(re.findall(r"url\(fonts/([^)]+)\)", css))
    assert fonts and all((film / "vendor/katex/fonts" / f).is_file() for f in fonts)


def test_scaffold_never_overwrites_the_film(tmp_path):
    subprocess.run(["bash", str(SCRIPT), str(tmp_path), "demo", "motion"], check=True,
                   capture_output=True)
    film = tmp_path / "demo" / "film" / "film.js"
    film.write_text("// mine")
    timeline = tmp_path / "demo" / "timeline.json"
    timeline.write_text('{"duration": 3}')
    scaffold = SCRIPT.parent / "scaffold_motion.sh"
    r = subprocess.run(["bash", str(scaffold), str(tmp_path / "demo"), "--update"],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert film.read_text() == "// mine"
    assert json.loads(timeline.read_text()) == {"duration": 3}


def test_update_refreshes_engine_files(tmp_path):
    subprocess.run(["bash", str(SCRIPT), str(tmp_path), "demo", "motion"], check=True,
                   capture_output=True)
    core = tmp_path / "demo" / "film" / "core.js"
    core.write_text("// stale")
    scaffold = SCRIPT.parent / "scaffold_motion.sh"
    subprocess.run(["bash", str(scaffold), str(tmp_path / "demo")], check=True, capture_output=True)
    assert core.read_text() == "// stale", "a plain re-run keeps the project's engine copy"
    subprocess.run(["bash", str(scaffold), str(tmp_path / "demo"), "--update"], check=True,
                   capture_output=True)
    assert core.read_text() != "// stale"


def test_other_engines_are_recorded_without_scaffolding(tmp_path):
    r = subprocess.run(["bash", str(SCRIPT), str(tmp_path), "demo", "manim"],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "demo" / "manifest.json").read_text())["engine"] == "manim"
    assert not (tmp_path / "demo" / "film").exists()


def test_rejects_unknown_engine(tmp_path):
    r = subprocess.run(["bash", str(SCRIPT), str(tmp_path), "demo", "bogus"],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 2
    assert not (tmp_path / "demo").exists()
