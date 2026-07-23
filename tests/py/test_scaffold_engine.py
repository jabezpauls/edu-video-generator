import subprocess

from conftest import SCRIPTS


def run(*args):
    return subprocess.run(["bash", str(SCRIPTS / "scaffold_engine.sh"), *args],
                          capture_output=True, text=True, check=False)


def test_manim_scaffold_copies_helpers(tmp_path):
    r = run(str(tmp_path), "manim")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "scenes" / "springs.py").is_file()
    assert (tmp_path / "scenes" / "formats.py").is_file()


def test_remotion_scaffold_copies_helpers(tmp_path):
    r = run(str(tmp_path), "remotion")
    assert r.returncode == 0, r.stderr
    for f in ("springs.ts", "formats.ts", "SceneFormats.tsx"):
        assert (tmp_path / "scenes" / "src" / f).is_file()


def test_existing_files_are_kept_unless_forced(tmp_path):
    run(str(tmp_path), "manim")
    f = tmp_path / "scenes" / "springs.py"
    f.write_text("# mine\n")
    assert "keep" in run(str(tmp_path), "manim").stdout
    assert f.read_text() == "# mine\n"
    run(str(tmp_path), "manim", "--force")
    assert f.read_text() != "# mine\n"


def test_unknown_engine(tmp_path):
    assert run(str(tmp_path), "motion2").returncode == 2
