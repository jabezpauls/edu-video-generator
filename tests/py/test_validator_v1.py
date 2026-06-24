"""Back-compat: storyboards in the original shape keep validating."""
import copy
import subprocess
import sys

from conftest import SCRIPTS


def test_v1_storyboard_is_valid(validator, v1_storyboard):
    assert validator.manual_check(v1_storyboard) == []


def test_missing_top_level_fields_reported(validator, v1_storyboard):
    del v1_storyboard["title"]
    del v1_storyboard["fps"]
    errs = validator.manual_check(v1_storyboard)
    assert "missing top-level field: title" in errs
    assert "missing top-level field: fps" in errs


def test_unknown_engine_rejected(validator, v1_storyboard):
    v1_storyboard["engine"] = "blender"
    assert any("engine must be" in e for e in validator.manual_check(v1_storyboard))


def test_empty_scenes_rejected(validator, v1_storyboard):
    v1_storyboard["scenes"] = []
    assert any("non-empty" in e for e in validator.manual_check(v1_storyboard))


def test_duplicate_scene_ids(validator, v1_storyboard):
    v1_storyboard["scenes"][1]["id"] = "01"
    assert any("duplicate id" in e for e in validator.manual_check(v1_storyboard))


def test_bad_element_kind_and_position(validator, v1_storyboard):
    els = v1_storyboard["scenes"][0]["elements"]
    els.append({"kind": "hologram", "position": "center"})
    els.append({"kind": "text", "position": "middle"})
    errs = validator.manual_check(v1_storyboard)
    assert any("bad kind 'hologram'" in e for e in errs)
    assert any("bad position 'middle'" in e for e in errs)


def test_beats_must_ascend(validator, v1_storyboard):
    v1_storyboard["scenes"][0]["beats"] = [
        {"t": 4, "action": "write"},
        {"t": 1, "action": "write"},
    ]
    assert any("ascending" in e for e in validator.manual_check(v1_storyboard))


def test_beat_needs_t_and_action(validator, v1_storyboard):
    v1_storyboard["scenes"][0]["beats"] = [{"action": "write"}]
    assert any("needs t and action" in e for e in validator.manual_check(v1_storyboard))


def test_duration_outside_tolerance(validator, v1_storyboard):
    v1_storyboard["target_duration_s"] = 60
    assert any("outside +/-15%" in e for e in validator.manual_check(v1_storyboard))


def test_duration_within_tolerance(validator, v1_storyboard):
    v1_storyboard["target_duration_s"] = 22  # 20s total, within 15%
    assert validator.manual_check(v1_storyboard) == []


def test_input_not_mutated(validator, v1_storyboard):
    before = copy.deepcopy(v1_storyboard)
    validator.manual_check(v1_storyboard)
    assert v1_storyboard == before


def run_cli(project):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_storyboard.py"), str(project)],
        capture_output=True, text=True,
    )


def test_cli_ok(write_project, v1_storyboard):
    r = run_cli(write_project(v1_storyboard))
    assert r.returncode == 0, r.stderr
    assert "storyboard OK: 2 scenes" in r.stdout


def test_cli_invalid_exits_nonzero(write_project, v1_storyboard):
    v1_storyboard["engine"] = "nope"
    r = run_cli(write_project(v1_storyboard))
    assert r.returncode == 1
    assert "INVALID" in r.stderr


def test_cli_missing_file(tmp_path):
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "not found" in r.stderr


def test_cli_bad_json(tmp_path):
    (tmp_path / "storyboard.json").write_text("{not json")
    r = run_cli(tmp_path)
    assert r.returncode == 1
    assert "JSON parse error" in r.stderr


def test_non_numeric_values_are_errors_not_crashes(validator, v1_storyboard):
    v1_storyboard["scenes"][0]["beats"][0]["t"] = "soon"
    v1_storyboard["scenes"][1]["est_duration_s"] = "ten"
    errs = validator.manual_check(v1_storyboard)
    assert any("t must be a number" in e for e in errs)
    assert any("est_duration_s must be a number" in e for e in errs)


def test_non_object_inputs(validator, v1_storyboard):
    assert validator.manual_check([]) == ["storyboard must be a JSON object"]
    v1_storyboard["scenes"][0] = "scene one"
    assert any("must be an object" in e for e in validator.manual_check(v1_storyboard))
