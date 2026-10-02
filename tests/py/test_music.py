import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS, load_script

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
pytest.importorskip("scipy")


@pytest.fixture(scope="module")
def music():
    return load_script("music")


def test_segments_cut_at_scene_boundaries_and_split_long_scenes(music):
    segs = music.plan_segments([5.0, 20.0], 30.0, bar_s=4.0)
    starts = [round(s[0], 3) for s in segs]
    assert 5.0 in starts and 20.0 in starts and starts[0] == 0.0
    assert segs[-1][1] == 30.0
    # contiguous, and chord spans stay within 1.5 two-bar steps
    assert all(abs(a[1] - b[0]) < 1e-9 for a, b in zip(segs, segs[1:]))
    assert max(s[1] - s[0] for s in segs) <= 12.0 + 1e-6
    assert [s[2] for s in segs if s[0] in (5.0, 20.0)] == [True, True]


def test_chord_notes_are_in_a_sane_register(music):
    for root in range(12):
        for q in music.QUALITY:
            bass, tones = music.chord_notes(root, q)
            assert 36 <= bass < 48 and all(55 <= t <= 90 for t in tones), (root, q, tones)


@pytest.mark.parametrize("mood", ["calm", "curious", "upbeat"])
def test_render_is_quiet_clean_and_deterministic(music, mood):
    a = music.render(6.0, [3.0], mood, seed=1)
    b = music.render(6.0, [3.0], mood, seed=1)
    c = music.render(6.0, [3.0], mood, seed=2)
    assert a.shape == (6 * music.SR, 2) and a.dtype == np.float32
    assert np.isfinite(a).all() and np.abs(a).max() <= 0.9 + 1e-6
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    rms_db = 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)))
    assert rms_db == pytest.approx(music.BED_RMS_DB, abs=0.5)
    assert np.abs(a[:200]).max() < 0.01 and np.abs(a[-200:]).max() < 0.01  # fades in and out


def test_moods_differ(music):
    a, b = (music.render(5.0, [], m, seed=3) for m in ("calm", "upbeat"))
    assert not np.allclose(a, b)


def test_cli_writes_bed_from_grid_and_none_removes_it(tmp_path):
    (tmp_path / "grid.json").write_text(json.dumps(
        {"duration": 4.0, "scenes": [{"start": 0.0}, {"start": 2.0}]}))
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "music.py"), str(tmp_path), *a],
                                    capture_output=True, text=True)
    r = run("--mood", "calm")
    assert r.returncode == 0, r.stderr
    data, sr = sf.read(tmp_path / "audio" / "music.wav")
    assert sr == 48000 and data.shape == (4 * 48000, 2)
    assert run("--mood", "none").returncode == 0
    assert not (tmp_path / "audio" / "music.wav").exists()


def test_cli_needs_a_duration(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "music.py"), str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "grid.json" in r.stderr


def test_mood_comes_from_the_flag_then_the_preset_then_the_mode(tmp_path):
    cfg = load_script("projectcfg")
    assert cfg.music_mood(str(tmp_path)) == "curious"
    (tmp_path / "storyboard.json").write_text('{"mode": "short"}')
    assert cfg.music_mood(str(tmp_path)) == "upbeat"
    (tmp_path / "preset.json").write_text('{"music": {"mood": "calm"}}')
    assert cfg.music_mood(str(tmp_path)) == "calm"
    assert cfg.music_mood(str(tmp_path), "none") == "none"
