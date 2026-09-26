"""Short mode: hook inside 3 s, 9x16, one idea. The shipped template and example must pass."""
import copy
import json

import pytest

from conftest import SKILL

TEMPLATE = SKILL / "templates" / "short.storyboard.json"


@pytest.fixture
def short():
    return json.loads(TEMPLATE.read_text())


def test_the_template_is_a_valid_short(validator, short):
    errs, warns = validator.check(short)
    assert errs == [] and warns == []
    assert short["mode"] == "short" and short["formats"] == ["9x16"] and short["engine"] == "motion"


def test_effective_defaults_for_a_short_that_names_nothing(validator, short):
    del short["formats"]
    assert validator.effective(short)["formats"] == ["9x16"]


def test_a_long_hook_narration_is_rejected(validator, short):
    short["scenes"][0]["narration"] = "Today we are going to look at an interesting question about how searching works"
    errs, _ = validator.check(short)
    assert any("hook must be spoken within 3 s" in e for e in errs)


def test_a_long_hook_scene_is_rejected(validator, short):
    short["scenes"][0]["est_duration_s"] = 9
    short["scenes"][1]["est_duration_s"] = 8
    errs, _ = validator.check(short)
    assert any("too long for a hook" in e for e in errs)


def test_the_hook_needs_something_on_frame_zero(validator, short):
    short["scenes"][0]["beats"] = [{"t": 2.0, "action": "pop_in", "target": "hook"}]
    errs, _ = validator.check(short)
    assert any("beat at t <= 1 s" in e for e in errs)
    short["scenes"][0]["beats"] = [{"on": "why", "action": "pop_in", "target": "hook"}]
    assert not any("beat at t" in e for e in validator.check(short)[0])


def test_warnings_for_a_short_without_9x16_narration_or_focus(validator, short):
    s = copy.deepcopy(short)
    s["formats"] = ["1x1"]
    s["narration"] = False
    s["scenes"] += [copy.deepcopy(s["scenes"][-1]) | {"id": f"1{i}"} for i in range(5)]
    for sc in s["scenes"]:
        sc["est_duration_s"] = s["target_duration_s"] / len(s["scenes"])
    errs, warns = validator.check(s)
    joined = " ".join(warns)
    assert "no 9x16" in joined and "narration is off" in joined and "more than one idea" in joined


def test_a_lesson_is_not_held_to_the_hook_rules(validator, short):
    short["mode"] = "lesson"
    short["scenes"][0]["narration"] = "word " * 40
    short["scenes"][0]["beats"] = []
    assert validator.check(short)[0] == []


def test_manifest_follows_the_storyboard(validator, short, tmp_path):
    (tmp_path / "storyboard.json").write_text(json.dumps(short))
    (tmp_path / "manifest.json").write_text(json.dumps({"slug": "x", "mode": "lesson", "formats": ["16x9"],
                                                        "engine": None, "preset": None, "phase": "intake"}))
    import subprocess, sys
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "validate_storyboard.py"), str(tmp_path), "--manifest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert (m["mode"], m["formats"], m["engine"], m["phase"]) == ("short", ["9x16"], "motion", "intake")
