"""Keep references/storyboard-schema.md honest: its examples must pass the validator."""
import json
import re

from conftest import SKILL


def doc():
    return (SKILL / "references" / "storyboard-schema.md").read_text()


def strip_jsonc(text):
    # the example only uses whole-line or trailing "  // comment" notes
    return re.sub(r"(?m)\s+//.*$", "", text)


def test_schema_example_parses_and_validates(validator):
    block = re.search(r"```jsonc\n(.*?)```", doc(), re.S).group(1)
    sb = json.loads(strip_jsonc(block))
    sb["target_duration_s"] = 12  # the example documents shape, not a real runtime
    errs, warns = validator.check(sb)
    assert errs == [] and warns == []
    assert sb["mode"] == "lesson" and sb["formats"] == ["16x9", "9x16"]
    assert any("on" in b for b in sb["scenes"][0]["beats"])


def test_good_scene_example_validates(validator, v1_storyboard):
    good = re.search(r"\*\*Good scene\*\*.*?```json\n(.*?)```", doc(), re.S).group(1)
    v1_storyboard["scenes"] = [json.loads(good)]
    v1_storyboard["target_duration_s"] = 7
    assert validator.manual_check(v1_storyboard) == []


def test_every_documented_format_and_mode_is_accepted(validator):
    text = doc()
    for fmt in validator.FORMATS:
        assert f"`{fmt}`" in text
    for mode in validator.MODES:
        assert f"`{mode}`" in text
