import json
import shutil
import subprocess
import sys

import pytest

from conftest import SCRIPTS, load_script

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
signal = pytest.importorskip("scipy.signal")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

SR = 48000


@pytest.fixture(scope="module")
def mix():
    return load_script("mix")


def speechlike(seconds, sr=22050, seed=0):
    """Band-limited noise with a syllable-rate envelope: close enough to speech for levels."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    x = signal.sosfilt(signal.butter(2, [200, 3000], "band", fs=sr, output="sos"),
                       rng.standard_normal(len(t)))
    env = 0.55 + 0.45 * np.sin(2 * np.pi * 4 * t) ** 2
    x *= env
    return (0.3 * x / np.abs(x).max()).astype(np.float32), sr


def bed(seconds, seed=1):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t) for f in (220, 277.2, 329.6)) / 3
    x += 0.05 * rng.standard_normal(n)
    return np.stack([x, x], 1).astype(np.float32) * 0.3


def clicks(seconds, times):
    n = int(seconds * SR)
    x = np.zeros((n, 2), dtype=np.float32)
    for t in times:
        i = int(t * SR)
        k = np.arange(2000) / SR
        x[i:i + 2000] += (np.sin(2 * np.pi * 1500 * k) * np.exp(-k * 80))[:, None] * 0.8
    return x


def make_project(tmp_path, music=True, sfx=True, vo=True, dur=12.0, vo_at=(1.0, 7.0)):
    """Two narrated scenes: speech at 1-4 s and 7-10 s on a 12 s grid."""
    adir = tmp_path / "audio"
    adir.mkdir()
    scenes = []
    for n, start in enumerate(vo_at, 1):
        sid = f"{n:02d}"
        s0 = (n - 1) * 6.0
        scene = {"id": sid, "n": n, "start": s0, "end": s0 + 6.0, "duration": 6.0,
                 "audio": None, "audio_start": None, "words": []}
        if vo:
            x, sr = speechlike(3.0, seed=n)
            sf.write(adir / f"scene_{sid}.wav", x, sr)
            scene.update(audio=f"audio/scene_{sid}.wav", audio_start=start)
        scenes.append(scene)
    (tmp_path / "grid.json").write_text(json.dumps({"duration": dur, "scenes": scenes}))
    if music:
        sf.write(adir / "music.wav", bed(dur), SR, subtype="FLOAT")
    if sfx:
        sf.write(adir / "sfx.wav", clicks(dur, [2.0, 5.0, 8.5]), SR, subtype="FLOAT")
    return tmp_path


def run(project, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / "mix.py"), str(project), *args],
                          capture_output=True, text=True)


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12)


def test_vo_graph_places_each_scene_at_its_start(mix):
    graph, label = mix.vo_graph([(0, 1.0), (1, 7.5)], 12.0)
    assert "adelay=48000S" in graph and "adelay=360000S" in graph
    assert "amix=inputs=2:normalize=0" in graph and label == "[vo]"


@pytest.mark.parametrize("parts", [
    dict(), dict(sfx=False), dict(music=False), dict(music=False, sfx=False),
    dict(vo=False, sfx=False)])
def test_master_hits_target_loudness_and_true_peak(tmp_path, parts):
    p = make_project(tmp_path, **parts)
    r = run(p)
    assert r.returncode == 0, r.stdout + r.stderr
    out = p / "audio" / "mix.wav"
    info = sf.info(out)
    assert (info.samplerate, info.channels, info.subtype) == (SR, 2, "PCM_24")
    assert info.duration == pytest.approx(12.0, abs=0.05)
    rep = json.loads((p / "audio" / "mix_report.json").read_text())
    assert abs(rep["integrated_lufs"] + 14) <= 0.5 and rep["true_peak_dbtp"] <= -1.0
    # independent measurement, not the script's own report
    I, TP, _ = load_script("mix").measure(str(out))
    assert abs(I + 14) <= 0.5 and TP <= -1.0


def test_narration_lands_on_the_grid_clock(tmp_path):
    p = make_project(tmp_path, music=False, sfx=False)
    assert run(p).returncode == 0
    vo, sr = sf.read(p / "audio" / "vo.wav")
    assert sr == SR and len(vo) == 12 * SR
    loud = np.abs(vo) > 0.01
    first = np.argmax(loud) / SR
    assert first == pytest.approx(1.0, abs=0.05)
    assert np.abs(vo[int(4.5 * SR):int(6.9 * SR)]).max() < 1e-4   # silence between the scenes
    assert np.abs(vo[int(7.2 * SR):int(9.8 * SR)]).max() > 0.01


def test_music_ducks_under_narration(tmp_path):
    p = make_project(tmp_path, sfx=False)
    assert run(p, "--stems").returncode == 0
    music, _ = sf.read(p / "audio" / "stems" / "music.wav")
    speech = rms_db(music[int(1.6 * SR):int(3.6 * SR)])
    gap = rms_db(music[int(4.8 * SR):int(6.6 * SR)])
    assert gap - speech >= 5.0, (gap, speech)
    assert gap - speech <= 14.0   # a duck, not a mute


def test_no_duck_flag_and_levels(tmp_path):
    p = make_project(tmp_path, sfx=False)
    assert run(p, "--stems", "--no-duck").returncode == 0
    music, _ = sf.read(p / "audio" / "stems" / "music.wav")
    assert abs(rms_db(music[int(1.6 * SR):int(3.6 * SR)]) - rms_db(music[int(4.8 * SR):int(6.6 * SR)])) < 1.0
    # the bed is levelled well below the voice
    vo, _ = sf.read(p / "audio" / "stems" / "vo.wav")
    assert rms_db(vo[int(1.5 * SR):int(3.5 * SR)]) - rms_db(music[int(4.8 * SR):int(6.6 * SR)]) > 10
    # mix.json and flags move the bed
    (p / "mix.json").write_text(json.dumps({"music": -10}))
    run(p, "--stems", "--no-duck")
    louder, _ = sf.read(p / "audio" / "stems" / "music.wav")
    assert rms_db(louder[int(4.8 * SR):int(6.6 * SR)]) - rms_db(music[int(4.8 * SR):int(6.6 * SR)]) == pytest.approx(7, abs=1)
    run(p, "--stems", "--no-duck", "--music", "-30")
    quiet, _ = sf.read(p / "audio" / "stems" / "music.wav")
    assert rms_db(quiet[int(4.8 * SR):int(6.6 * SR)]) < rms_db(music[int(4.8 * SR):int(6.6 * SR)])


def test_custom_target(tmp_path):
    p = make_project(tmp_path)
    assert run(p, "--target", "-16").returncode == 0
    rep = json.loads((p / "audio" / "mix_report.json").read_text())
    assert abs(rep["integrated_lufs"] + 16) <= 0.5


def test_errors(tmp_path):
    r = run(tmp_path)
    assert r.returncode == 1 and "grid.json" in r.stderr
    (tmp_path / "grid.json").write_text(json.dumps({"duration": 5, "scenes": []}))
    r = run(tmp_path)
    assert r.returncode == 1 and "nothing to mix" in r.stderr


def test_preset_moves_the_levels_and_can_drop_the_sfx(mix, tmp_path):
    ns = type("A", (), dict(music=None, sfx=None, vo=None, target=None, no_duck=False))
    assert mix.load_levels(str(tmp_path), ns)["sfx"] == -9.0
    (tmp_path / "preset.json").write_text(json.dumps({"music": {"level_db": -3}, "sfx": {"level_db": -2, "enabled": False}}))
    lv = mix.load_levels(str(tmp_path), ns)
    assert (lv["music"], lv["sfx"], lv.get("sfx_off")) == (-20.0, -11.0, True)
    (tmp_path / "mix.json").write_text('{"sfx": -5}')
    assert mix.load_levels(str(tmp_path), ns)["sfx"] == -5, "mix.json beats the preset"
