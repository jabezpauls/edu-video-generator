"""Beat `on` anchors (word / cue references resolved against the narration grid later)."""
import pytest


def set_beats(sb, beats, scene=0):
    sb["scenes"][scene]["beats"] = beats
    return sb


@pytest.mark.parametrize(
    "anchor",
    [
        "derivative",
        "derivative#2",
        "w12",
        "p2",
        "start",
        "end",
        "s01.derivative",
        "s01.derivative#2",
        "s1.end",
        "don't",
        "well-known",
        "π",
        "naïve",
    ],
)
def test_valid_anchors(validator, v1_storyboard, anchor):
    set_beats(v1_storyboard, [{"on": anchor, "action": "write", "target": "equation"}])
    assert validator.check(v1_storyboard) == ([], [])


@pytest.mark.parametrize(
    "anchor",
    ["", " ", "two words", "s01.", ".end", "word#", "word#0", "word#x", "s01..end", "-dash", 3, None, ["a"]],
)
def test_invalid_anchors(validator, v1_storyboard, anchor):
    set_beats(v1_storyboard, [{"on": anchor, "action": "write"}])
    errs = validator.manual_check(v1_storyboard)
    assert any("on must be a word or cue" in e for e in errs), errs


def test_anchor_replaces_t(validator, v1_storyboard):
    set_beats(v1_storyboard, [{"on": "rotates", "action": "indicate"}])
    assert validator.manual_check(v1_storyboard) == []


def test_t_and_on_together_keep_t_ordering(validator, v1_storyboard):
    set_beats(
        v1_storyboard,
        [
            {"t": 4, "on": "rotates", "action": "write"},
            {"t": 1, "on": "ninety", "action": "write"},
        ],
    )
    assert any("ascending" in e for e in validator.manual_check(v1_storyboard))


def test_anchor_only_beats_do_not_break_t_ordering(validator, v1_storyboard):
    set_beats(
        v1_storyboard,
        [
            {"t": 2, "action": "write"},
            {"on": "rotates", "action": "write"},
            {"t": 3, "action": "write"},
        ],
    )
    assert validator.manual_check(v1_storyboard) == []


def test_beat_with_neither_t_nor_on(validator, v1_storyboard):
    set_beats(v1_storyboard, [{"action": "write"}])
    assert any("needs t (or on)" in e for e in validator.manual_check(v1_storyboard))


def test_beat_with_on_but_no_action(validator, v1_storyboard):
    set_beats(v1_storyboard, [{"on": "rotates"}])
    assert any("needs t (or on) and action" in e for e in validator.manual_check(v1_storyboard))


def test_cue_for_missing_scene_is_error(validator, v1_storyboard):
    set_beats(v1_storyboard, [{"on": "s09.end", "action": "write"}])
    assert any("scene s09" in e and "does not exist" in e for e in validator.manual_check(v1_storyboard))


def test_cue_for_other_scene_warns(validator, v1_storyboard):
    set_beats(v1_storyboard, [{"on": "s02.end", "action": "write"}])
    errs, warns = validator.check(v1_storyboard)
    assert errs == []
    assert len(warns) == 1 and "another scene" in warns[0]


def test_cue_prefix_matches_zero_padded_id_numerically(validator, v1_storyboard):
    set_beats(v1_storyboard, [{"on": "s1.end", "action": "write"}])
    assert validator.check(v1_storyboard) == ([], [])


def test_cli_prints_warnings_but_passes(write_project, v1_storyboard):
    from test_validator_v1 import run_cli

    set_beats(v1_storyboard, [{"on": "s02.end", "action": "write"}])
    r = run_cli(write_project(v1_storyboard))
    assert r.returncode == 0
    assert "warning:" in r.stderr
