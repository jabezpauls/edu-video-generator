"""The Manim helper must resolve anchors exactly like grid.py does."""
import importlib.util
import json
import sys
import types

import pytest

from conftest import SKILL, load_script
from test_grid import STORY, make


@pytest.fixture(scope="module")
def gridsync():
    fake = types.ModuleType("manim")
    fake.Scene = type("Scene", (), {"setup": lambda self: None})
    sys.modules.setdefault("manim", fake)
    spec = importlib.util.spec_from_file_location("gridsync", SKILL / "templates" / "gridsync.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def grid_file(tmp_path):
    g = make(load_script("grid"), lead=0.4)
    p = tmp_path / "grid.json"
    p.write_text(json.dumps(g))
    return p, g


def test_every_cue_matches_grid_resolution(gridsync, grid_file):
    path, g = grid_file
    grid = load_script("grid")
    for sid in ("01", "02"):
        gs = gridsync.Grid(sid, path)
        for anchor in ("w0", "w3", "p1", "p2", "start", "end", "rotates", "rotates#2", "rotates#1",
                       "s02.line", "s01.p2"):
            try:
                want = grid.resolve(g, anchor, sid) - gs.start
            except grid.GridError:
                with pytest.raises(KeyError):
                    gs.cue(anchor)
                continue
            assert gs.cue(anchor) == pytest.approx(want), (sid, anchor)


def test_reserved_word_and_duration(gridsync, grid_file):
    path, g = grid_file
    gs = gridsync.Grid("02", path)
    assert gs.cue("end#1") == pytest.approx(g["cues"]["s02.end#1"] - gs.start)
    assert gs.cue("end") > gs.cue("end#1")
    assert gs.duration == g["scenes"][1]["duration"] and gs.fps == 30


def test_unknown_cue_names_what_it_looked_for(gridsync, grid_file):
    gs = gridsync.Grid("01", grid_file[0])
    with pytest.raises(KeyError, match="s01.zebra"):
        gs.cue("zebra")
