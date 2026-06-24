import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "educational-video" / "scripts"


def load_script(name: str):
    """Import a script from the skill's scripts/ dir by file name (without .py)."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def validator():
    return load_script("validate_storyboard")


@pytest.fixture
def v1_storyboard():
    """A minimal storyboard in the original (v1) shape."""
    return {
        "title": "Complex rotation",
        "audience": "undergrad",
        "aspect_ratio": "16:9",
        "resolution": "1920x1080",
        "fps": 30,
        "engine": "manim",
        "engine_reason": "math rigor",
        "language": "en",
        "narration": True,
        "target_duration_s": 20,
        "scenes": [
            {
                "id": "01",
                "title": "Rotation",
                "narration": "Multiplying by i rotates the point ninety degrees.",
                "template": "EquationReveal",
                "elements": [
                    {"kind": "equation", "tex": "i(a+bi)=-b+ai", "position": "center"}
                ],
                "beats": [
                    {"t": 0, "action": "write", "target": "equation"},
                    {"t": 3, "action": "indicate", "target": "equation"},
                ],
                "est_duration_s": 10,
                "assets": [],
            },
            {
                "id": "02",
                "title": "Recap",
                "narration": "So i is a quarter turn.",
                "template": "TitleCard",
                "elements": [{"kind": "text", "value": "Quarter turn", "position": "top"}],
                "beats": [{"t": 0, "action": "fade_in", "target": "Quarter turn"}],
                "est_duration_s": 10,
                "assets": [],
            },
        ],
    }


@pytest.fixture
def write_project(tmp_path):
    """Write a storyboard dict to a temp project dir and return the dir."""

    def _write(sb):
        (tmp_path / "storyboard.json").write_text(json.dumps(sb))
        return tmp_path

    return _write
