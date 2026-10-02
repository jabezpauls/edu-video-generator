"""Storyboard v2: mode, formats, preset, engine=motion."""
import pytest


@pytest.fixture
def v2(v1_storyboard):
    v1_storyboard.update(
        {"engine": "motion", "mode": "lesson", "formats": ["16x9", "9x16"], "preset": "chalkboard"}
    )
    return v1_storyboard


def test_v2_storyboard_is_valid(validator, v2):
    assert validator.manual_check(v2) == []


@pytest.mark.parametrize("engine", ["manim", "remotion", "motion"])
def test_all_engines_accepted(validator, v1_storyboard, engine):
    v1_storyboard["engine"] = engine
    assert validator.manual_check(v1_storyboard) == []


def test_engine_error_lists_motion(validator, v1_storyboard):
    v1_storyboard["engine"] = "blender"
    (err,) = validator.manual_check(v1_storyboard)
    assert "motion" in err


def test_null_engine_still_allowed_before_selection(validator, v1_storyboard):
    v1_storyboard["engine"] = None
    assert validator.manual_check(v1_storyboard) == []


@pytest.mark.parametrize("mode", ["lesson", "short"])
def test_modes(validator, v2, mode):
    v2["mode"] = mode
    if mode == "short":
        v2["target_duration_s"] = 45
        v2["scenes"][0]["est_duration_s"] = 4
        v2["scenes"][0]["narration"] = "Why does halving win?"
        v2["scenes"][1]["est_duration_s"] = 41
    assert validator.manual_check(v2) == [], validator.manual_check(v2)


def test_bad_mode(validator, v2):
    v2["mode"] = "podcast"
    assert any("mode must be" in e for e in validator.manual_check(v2))


@pytest.mark.parametrize("fmt", ["16x9", "1x1", "4x5", "9x16"])
def test_each_format_valid(validator, v2, fmt):
    v2["formats"] = [fmt]
    assert validator.manual_check(v2) == []


def test_bad_formats(validator, v2):
    v2["formats"] = ["16x9", "21x9"]
    assert any("unknown entries ['21x9']" in e for e in validator.manual_check(v2))


def test_formats_must_be_non_empty_list(validator, v2):
    for bad in ([], "16x9", None):
        v2["formats"] = bad
        assert any("non-empty array" in e for e in validator.manual_check(v2)), bad


def test_duplicate_formats(validator, v2):
    v2["formats"] = ["9x16", "9x16"]
    assert any("duplicate" in e for e in validator.manual_check(v2))


@pytest.mark.parametrize("preset", ["blank", "chalkboard", "paper", "blueprint", "my-brand_2"])
def test_preset_slugs(validator, v2, preset):
    v2["preset"] = preset
    assert validator.manual_check(v2) == []


@pytest.mark.parametrize("preset", ["", "Chalk Board", "../etc", 7])
def test_bad_preset(validator, v2, preset):
    v2["preset"] = preset
    assert any("preset must be" in e for e in validator.manual_check(v2))


def test_null_preset_means_default(validator, v2):
    v2["preset"] = None
    assert validator.manual_check(v2) == []


def test_short_duration_window(validator, v2):
    v2["mode"] = "short"
    errs = validator.manual_check(v2)  # target is 20s
    assert any("short mode" in e and "30-60" in e for e in errs)


def test_palette_hex_validation(validator, v2):
    v2["palette"] = {"bg": "#0e1116", "accent": "#58a6ff", "ink": "#fff"}
    assert validator.manual_check(v2) == []
    v2["palette"]["accent"] = "blue"
    assert any("palette.accent" in e for e in validator.manual_check(v2))
    v2["palette"] = ["#000"]
    assert any("palette must be an object" in e for e in validator.manual_check(v2))


class TestEffective:
    def test_v1_gets_lesson_defaults(self, validator, v1_storyboard):
        assert validator.effective(v1_storyboard) == {
            "mode": "lesson", "formats": ["16x9"], "preset": None,
        }

    def test_short_defaults_to_vertical(self, validator, v1_storyboard):
        v1_storyboard["mode"] = "short"
        eff = validator.effective(v1_storyboard)
        assert eff["formats"] == ["9x16"]

    def test_explicit_formats_win(self, validator, v1_storyboard):
        v1_storyboard.update({"mode": "short", "formats": ["1x1"]})
        assert validator.effective(v1_storyboard)["formats"] == ["1x1"]

    def test_defaults_are_copies(self, validator, v1_storyboard):
        validator.effective(v1_storyboard)["formats"].append("1x1")
        assert validator.effective(v1_storyboard)["formats"] == ["16x9"]
