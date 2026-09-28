"""The example storyboards stay valid, and show the v2 features they claim to."""
import json

import pytest

from conftest import SKILL

EXAMPLES = SKILL.parent.parent / "examples"
FILES = sorted(EXAMPLES.glob("*.storyboard.json"))


def test_there_is_a_lesson_and_a_short():
    modes = {json.loads(f.read_text())["mode"] for f in FILES}
    assert modes == {"lesson", "short"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_example_validates_with_no_warnings(validator, path):
    sb = json.loads(path.read_text())
    errs, warns = validator.check(sb)
    assert errs == [] and warns == []
    assert all("on" in b for sc in sb["scenes"] for b in sc["beats"] if "t" not in b)


def test_the_example_presets_exist():
    for f in FILES:
        preset = json.loads(f.read_text())["preset"]
        assert (SKILL / "presets" / preset / "preset.jsonc").is_file()
