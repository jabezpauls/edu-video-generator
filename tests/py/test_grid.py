import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS, load_script


@pytest.fixture(scope="module")
def grid():
    return load_script("grid")


def words(text, step=0.4):
    """Evenly timed words (scene-local), one per token."""
    out, t = [], 0.0
    for tok in text.split():
        out.append({"word": tok, "start": round(t, 3), "end": round(t + step * 0.8, 3)})
        t += step
    return out


STORY = {
    "fps": 30,
    "scenes": [
        {"id": "01", "narration": "Multiplying by i rotates the point. Rotates it ninety degrees.",
         "est_duration_s": 5,
         "beats": [{"on": "rotates#2", "action": "pop_in", "target": "dot"},
                   {"t": 1.0, "action": "write", "target": "eq"}]},
        {"id": "02", "narration": "The end of the line.", "est_duration_s": 3,
         "beats": [{"on": "end#1", "action": "highlight", "target": "eq"},
                   {"on": "s01.p2", "action": "fade_in", "target": "x"}]},
        {"id": "03", "narration": "", "est_duration_s": 2.5, "beats": []},
    ],
}


def make(grid, **kw):
    def words_for(sc):
        return words(sc["narration"]), "provider", 0.0
    return grid.build(STORY, words_for, **kw)


def test_scene_timeline_is_contiguous_with_padding(grid):
    g = make(grid, lead=0.5, tail=1.0)
    s1, s2, s3 = g["scenes"]
    assert s1["start"] == 0 and s1["end"] == s2["start"] and s2["end"] == s3["start"]
    last = s1["words"][-1]["end"]
    assert s1["duration"] == pytest.approx(0.5 + (last - 0.5) + 1.0, abs=1e-3)
    assert s1["speech_start"] == pytest.approx(0.5)  # first word after the lead-in
    assert g["duration"] == pytest.approx(s3["end"])


def test_silent_scene_keeps_estimated_duration(grid):
    s3 = make(grid)["scenes"][2]
    assert s3["duration"] == 2.5 and s3["words"] == [] and s3["speech_start"] is None


def test_words_use_the_global_clock(grid):
    g = make(grid, lead=0.4)
    s2 = g["scenes"][1]
    assert s2["words"][0]["start"] == pytest.approx(s2["start"] + 0.4)


def test_named_cues(grid):
    g = make(grid, lead=0.4)
    c = g["cues"]
    assert c["s01.start"] == 0
    assert c["s01.w0"] == pytest.approx(0.4)
    assert c["s01.multiplying"] == c["s01.w0"]
    assert c["s01.rotates"] == c["s01.w3"]            # first occurrence
    assert c["s01.rotates#2"] == c["s01.w6"]          # second occurrence
    assert c["s01.p1"] == c["s01.w0"] and c["s01.p2"] == c["s01.w6"]
    assert c["s01.end"] == g["scenes"][0]["speech_end"]
    assert c["s02.start"] == g["scenes"][1]["start"]


def test_reserved_word_names_stay_reachable(grid):
    c = make(grid)["cues"]
    assert "s02.end#1" in c and c["s02.end"] > c["s02.end#1"]


def test_resolve_variants(grid):
    g = make(grid)
    assert grid.resolve(g, "rotates#2", "01") == g["cues"]["s01.rotates#2"]
    assert grid.resolve(g, "ROTATES", "01") == g["cues"]["s01.rotates"]
    assert grid.resolve(g, "rotates#1", "01") == g["cues"]["s01.rotates"]
    assert grid.resolve(g, "w3", "01") == g["cues"]["s01.w3"]
    assert grid.resolve(g, "p2", "01") == g["cues"]["s01.p2"]
    assert grid.resolve(g, "end", "02") == g["cues"]["s02.end"]
    assert grid.resolve(g, "end#1", "02") == g["cues"]["s02.end#1"]
    assert grid.resolve(g, "s2.line", "01") == g["cues"]["s02.line"]  # s2 == s02


@pytest.mark.parametrize("anchor, scene, msg", [
    ("nonsense", "01", "not in scene"),
    ("rotates#3", "01", "2 time"),
    ("w99", "01", "no word 99"),
    ("p9", "01", "no phrase 9"),
    ("s09.start", "01", "unknown scene"),
    ("rotates", None, "unknown scene"),
])
def test_resolve_errors(grid, anchor, scene, msg):
    with pytest.raises(grid.GridError, match=msg):
        grid.resolve(make(grid), anchor, scene)


def test_resolve_beats_prefers_on_over_t(grid):
    g = make(grid, lead=0.4)
    sb = json.loads(json.dumps(STORY))
    sb["scenes"][0]["beats"] = [{"t": 0.5, "on": "rotates", "action": "write", "target": "a"}]
    res = grid.resolve_beats(sb, g)
    b = res["scenes"][0]["beats"][0]
    assert b["source"] == "on" and b["t"] == pytest.approx(g["cues"]["s01.rotates"])
    assert b["at"] == pytest.approx(g["cues"]["s01.rotates"])


def test_resolve_beats_scene_local_and_global_times(grid):
    g = make(grid)
    res = grid.resolve_beats(STORY, g)
    b2 = res["scenes"][1]["beats"]
    start2 = g["scenes"][1]["start"]
    assert all(b["at"] == pytest.approx(start2 + b["t"]) for b in b2)
    # cross-scene anchor resolves on the global clock, so its local t is negative
    assert any(b["on"] == "s01.p2" and b["t"] < 0 for b in b2)


def test_resolve_beats_falls_back_to_t_and_reports_bad_anchors(grid):
    g = make(grid)
    sb = json.loads(json.dumps(STORY))
    sb["scenes"][0]["beats"] = [{"t": 1.0, "on": "nope", "action": "write", "target": "a"}]
    assert grid.resolve_beats(sb, g)["scenes"][0]["beats"][0]["source"] == "t"
    sb["scenes"][0]["beats"] = [{"on": "nope", "action": "write", "target": "a"}]
    with pytest.raises(grid.GridError, match="scene 01 beat 0"):
        grid.resolve_beats(sb, g)


def test_numeric_scene_lookup_by_number(grid):
    g = make(grid)
    assert grid._find_scene(g, "1")["id"] == "01"
    assert grid._find_scene(g, "7") is None


def test_cli_build_resolve_and_cue(tmp_path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "storyboard.json").write_text(json.dumps(STORY))
    for sid, text in (("01", STORY["scenes"][0]["narration"]), ("02", "The end of the line.")):
        (tmp_path / "audio" / f"scene_{sid}.words.json").write_text(json.dumps(words(text)))
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "grid.py"), *a],
                                    capture_output=True, text=True)
    r = run(str(tmp_path), "--no-asr", "--write-durations")
    assert r.returncode == 0, r.stderr
    g = json.loads((tmp_path / "grid.json").read_text())
    assert g["version"] == 1 and len(g["scenes"]) == 3
    sb = json.loads((tmp_path / "storyboard.json").read_text())
    assert sb["scenes"][0]["est_duration_s"] == pytest.approx(g["scenes"][0]["duration"], abs=0.06)
    assert run("resolve", str(tmp_path)).returncode == 0
    res = json.loads((tmp_path / "beats.resolved.json").read_text())
    assert res["scenes"][0]["beats"][0]["at"] > 0
    r = run("cue", str(tmp_path), "s01.rotates#2")
    assert float(r.stdout) == pytest.approx(g["cues"]["s01.rotates#2"], abs=1e-3)
    assert run("cue", str(tmp_path), "s01.zebra").returncode == 1


# ---- sfx plan ----

def plan(grid, story=STORY, **kw):
    g = make(grid, lead=0.4)
    res = grid.resolve_beats(story, g)
    return g, grid.sfx_cues(story, g, res, **kw)


def test_sfx_cues_follow_beats_and_scene_changes(grid):
    g, out = plan(grid)
    types = [(c["type"], c["what"]) for c in out["cues"]]
    assert ("pop", "pop_in dot") in types and ("whoosh", "scene 02 in") in types
    assert out["cues"] == sorted(out["cues"], key=lambda c: c["t"])
    pop = next(c for c in out["cues"] if c["what"] == "pop_in dot")
    assert pop["t"] == pytest.approx(g["cues"]["s01.rotates#2"], abs=1e-3)
    whoosh = next(c for c in out["cues"] if c["type"] == "whoosh")
    assert whoosh["t"] == pytest.approx(g["scenes"][1]["start"], abs=0.05)
    assert out["duration"] == g["duration"] and out["sr"] == 48000


def scene1_only():
    story = json.loads(json.dumps(STORY))
    story["scenes"][1]["beats"] = []
    return story


def test_sfx_beat_override_and_silence(grid):
    story = scene1_only()
    story["scenes"][0]["beats"] = [
        {"t": 1.0, "action": "write", "target": "eq", "sfx": "chime"},
        {"t": 2.0, "action": "pop_in", "target": "dot", "sfx": "none"},
        {"t": 3.0, "action": "mystery", "target": "q"}]
    _, out = plan(grid, story, transitions=False)
    assert [c["type"] for c in out["cues"]] == ["chime"]


def test_sfx_typing_on_code_ticks_and_close_hits_merge(grid):
    story = scene1_only()
    story["scenes"][0]["elements"] = [{"kind": "code", "label": "snippet", "value": "x"}]
    story["scenes"][0]["beats"] = [
        {"t": 1.0, "action": "write", "target": "snippet"},
        {"t": 1.03, "action": "pop_in", "target": "other"}]
    _, out = plan(grid, story, transitions=False)
    assert len(out["cues"]) == 1  # 30 ms apart: one sound, the louder one
    story["scenes"][0]["beats"] = [{"t": 1.0, "action": "write", "target": "snippet"}]
    assert plan(grid, story, transitions=False)[1]["cues"][0]["type"] == "tick"


def test_sfx_is_seeded(grid):
    assert plan(grid)[1] == plan(grid)[1]
    assert plan(grid)[1]["cues"][0]["pitch"] != plan(grid, seed=7)[1]["cues"][0]["pitch"]
