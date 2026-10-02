import json
import os
import stat
import subprocess
import sys

import pytest

from conftest import SCRIPTS, load_script


@pytest.fixture(scope="module")
def tts():
    return load_script("tts")


def test_words_from_chars_groups_on_whitespace(tts):
    chars = list("Hi, you")
    starts = [i * 0.1 for i in range(len(chars))]
    ends = [s + 0.1 for s in starts]
    out = tts.words_from_chars(chars, starts, ends)
    assert [w["word"] for w in out] == ["Hi,", "you"]
    assert out[0]["start"] == 0 and out[0]["end"] == pytest.approx(0.3)
    assert out[1]["start"] == pytest.approx(0.4) and out[1]["end"] == pytest.approx(0.7)


def test_words_from_chars_handles_runs_of_spaces_and_empty(tts):
    assert tts.words_from_chars([], [], []) == []
    out = tts.words_from_chars(list("a  b"), [0, 1, 2, 3], [1, 2, 3, 4])
    assert [w["word"] for w in out] == ["a", "b"]


def test_text_hash_changes_with_voice_and_text(tts):
    base = tts.text_hash("piper", "m", "v", "hello")
    assert base == tts.text_hash("piper", "m", "v", "hello")
    assert base != tts.text_hash("piper", "m", "v2", "hello")
    assert base != tts.text_hash("piper", "m", "v", "hello!")


def test_speakable_warnings(tts):
    assert tts.speakable_warnings("01", "e to the i pi equals minus one") == []
    assert tts.speakable_warnings("01", r"$e^{i\pi}=-1$")
    assert tts.speakable_warnings("01", "compute 3/4 first")


def test_cli_synthesizes_once_then_skips_unchanged(tmp_path):
    """Fake piper: writes a tiny wav; the second run must not call it again."""
    calls = tmp_path / "calls.txt"
    fake = tmp_path / "piper"
    fake.write_text(f"#!/bin/sh\necho x >> {calls}\ncat >/dev/null\n"
                    "while [ $# -gt 0 ]; do [ \"$1\" = --output_file ] && out=$2; shift; done\n"
                    "printf RIFF > \"$out\"\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    (tmp_path / ".videogen").mkdir()
    (tmp_path / ".videogen" / "env.json").write_text(json.dumps(
        {"tts": {"provider": "piper", "bin": str(fake), "model": "m"}}))
    (tmp_path / "storyboard.json").write_text(json.dumps(
        {"scenes": [{"id": "01", "narration": "Hello there."}, {"id": "02", "narration": ""}]}))
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "tts.py"), str(tmp_path), *a],
                                    capture_output=True, text=True)
    assert run().returncode == 0
    assert (tmp_path / "audio" / "scene_01.wav").exists()
    assert not (tmp_path / "audio" / "scene_02.wav").exists()
    assert len(calls.read_text().split()) == 1
    r = run()
    assert "unchanged" in r.stdout and len(calls.read_text().split()) == 1
    run("--force")
    assert len(calls.read_text().split()) == 2
    # editing the narration invalidates just that scene
    sb = json.loads((tmp_path / "storyboard.json").read_text())
    sb["scenes"][0]["narration"] = "Changed text."
    (tmp_path / "storyboard.json").write_text(json.dumps(sb))
    run()
    assert len(calls.read_text().split()) == 3


def _fake_piper(tmp_path):
    fake = tmp_path / "piper"
    fake.write_text("#!/bin/sh\necho \"$@\" >> " + str(tmp_path / "args.txt") + "\ncat >/dev/null\n"
                    "while [ $# -gt 0 ]; do [ \"$1\" = --output_file ] && out=$2; shift; done\n"
                    "printf RIFF > \"$out\"\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    (tmp_path / ".videogen").mkdir()
    (tmp_path / ".videogen" / "env.json").write_text(json.dumps({"tts": {"provider": "piper", "bin": str(fake)}}))
    (tmp_path / "storyboard.json").write_text(json.dumps({"scenes": [{"id": "01", "narration": "Hello there."}]}))


def test_the_presets_piper_voice_is_used_when_it_is_downloaded(tmp_path):
    _fake_piper(tmp_path)
    (tmp_path / "preset.json").write_text(json.dumps({"voice": {"piper": "en_GB-alan-medium"}}))
    (tmp_path / "assets" / "tts").mkdir(parents=True)
    (tmp_path / "assets" / "tts" / "en_GB-alan-medium.onnx").write_text("x")
    r = subprocess.run([sys.executable, str(SCRIPTS / "tts.py"), str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "en_GB-alan-medium.onnx" in (tmp_path / "args.txt").read_text()


def test_a_preset_voice_that_is_not_downloaded_falls_back_with_a_warning(tmp_path):
    _fake_piper(tmp_path)
    (tmp_path / "preset.json").write_text(json.dumps({"voice": {"piper": "en_GB-alan-medium"}}))
    r = subprocess.run([sys.executable, str(SCRIPTS / "tts.py"), str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "en_GB-alan-medium is not in assets/tts" in r.stderr
    assert "en_US-amy-medium.onnx" in (tmp_path / "args.txt").read_text()
