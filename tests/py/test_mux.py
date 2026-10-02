import json
import shutil
import subprocess

import pytest

from conftest import SCRIPTS, load_script

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")


def lavfi_video(path, seconds, size="320x180"):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=s={size}:r=30:d={seconds}",
                    "-pix_fmt", "yuv420p", str(path)], capture_output=True, check=True)


def probe(path, entries):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True).stdout
    return out.split()


def make_project(root, durations=(4.0, 3.0), video_lengths=(4.0, 2.0), name="proj"):
    p = root / name
    (p / "audio").mkdir(parents=True)
    (p / "output").mkdir()
    scenes, t = [], 0.0
    rng = np.random.default_rng(0)
    for i, (d, vl) in enumerate(zip(durations, video_lengths), 1):
        sid = f"{i:02d}"
        scenes.append({"id": sid, "n": i, "start": t, "end": t + d, "duration": d,
                       "audio": f"audio/scene_{sid}.wav", "audio_start": t + 0.4, "words": []})
        x = rng.standard_normal(int(22050 * (d - 1.0))).astype(np.float32) * 0.1
        sf.write(p / "audio" / f"scene_{sid}.wav", x, 22050)
        lavfi_video(p / "output" / f"scene_{sid}.mp4", vl)
        t += d
    (p / "grid.json").write_text(json.dumps({"fps": 30, "duration": t, "scenes": scenes}))
    (p / "storyboard.json").write_text(json.dumps({"scenes": [{"id": s["id"]} for s in scenes]}))
    return p


def mux(project, *args):
    return subprocess.run(["bash", str(SCRIPTS / "mux.sh"), str(project), *args],
                          capture_output=True, text=True)


def test_mux_conforms_scenes_and_attaches_mastered_mix(tmp_path):
    p = make_project(tmp_path)
    r = mux(p)
    assert r.returncode == 0, r.stderr
    final = p / "output" / "final.mp4"
    assert "shorter than its narration slot" in r.stderr  # scene 02 render was 1 s short
    kinds = probe(final, "stream=codec_type")
    assert sorted(kinds) == ["audio", "video"]
    assert float(probe(final, "format=duration")[0]) == pytest.approx(7.0, abs=0.1)
    I, TP, _ = load_script("mix").measure(str(final))
    assert abs(I + 14) <= 0.5 and TP <= -1.0, (I, TP)


def test_mux_soft_subtitles_and_burn(tmp_path):
    p = make_project(tmp_path)
    (p / "output" / "subtitles.srt").write_text("1\n00:00:00,500 --> 00:00:02,000\nHello\n")
    assert mux(p).returncode == 0
    assert "subtitle" in probe(p / "output" / "final.mp4", "stream=codec_type")
    (p / "output" / "subtitles.ass").write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 320\nPlayResY: 180\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,20,&H00FFFFFF,&H00000000,&H80000000,0,3,1,2,10,10,10,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.50,0:00:02.00,Default,,0,0,0,,Hello\n")
    assert mux(p, "--burn").returncode == 0
    assert "subtitle" not in probe(p / "output" / "final.mp4", "stream=codec_type")


def test_mux_trims_a_long_render_and_works_in_a_quirky_path(tmp_path):
    p = make_project(tmp_path, video_lengths=(5.5, 3.0), name="it's a project")
    r = mux(p)
    assert r.returncode == 0, r.stderr
    assert "longer than its slot" in r.stderr
    assert float(probe(p / "output" / "final.mp4", "format=duration")[0]) == pytest.approx(7.0, abs=0.1)


def test_mux_remixes_when_inputs_change(tmp_path):
    p = make_project(tmp_path)
    assert mux(p).returncode == 0
    mix = p / "audio" / "mix.wav"
    first = mix.stat().st_mtime_ns
    assert "integrated" not in mux(p).stdout  # up to date: no remix
    assert mix.stat().st_mtime_ns == first
    sf.write(p / "audio" / "music.wav", np.zeros((7 * 48000, 2), dtype=np.float32) + 0.001, 48000)
    assert mux(p).returncode == 0
    assert mix.stat().st_mtime_ns > first


def test_mux_requires_grid_and_scene_videos(tmp_path):
    p = make_project(tmp_path)
    (p / "output" / "scene_02.mp4").unlink()
    r = mux(p)
    assert r.returncode == 1 and "missing scene video" in r.stderr
    (p / "grid.json").unlink()
    r = mux(p)
    assert r.returncode == 1 and "grid.json missing" in r.stderr


def test_mux_all_formats_names_the_primary_final_and_burns_9x16_captions(tmp_path):
    p = make_project(tmp_path)
    sb = json.loads((p / "storyboard.json").read_text())
    sb["formats"] = ["16x9", "9x16"]
    (p / "storyboard.json").write_text(json.dumps(sb))
    for sid, vl in (("01", 4.0), ("02", 3.0)):
        (p / "output" / f"scene_{sid}.mp4").rename(p / "output" / f"scene_{sid}.16x9.mp4")
        lavfi_video(p / "output" / f"scene_{sid}.9x16.mp4", vl, size="180x320")
    (p / "output" / "subtitles.srt").write_text("1\n00:00:00,500 --> 00:00:02,000\nHello\n")
    (p / "output" / "subtitles_9x16.ass").write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 180\nPlayResY: 320\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,16,&H00FFFFFF,&H00000000,&H80000000,0,2,1,2,10,10,60,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.50,0:00:02.00,Default,,0,0,0,,Hello\n")
    r = mux(p, "--format", "all")
    assert r.returncode == 0, r.stderr
    wide, tall = p / "output" / "final.mp4", p / "output" / "final_9x16.mp4"
    assert probe(wide, "stream=width,height")[:1] == ["320,180"] or "320,180" in probe(wide, "stream=width,height")
    assert "180,320" in probe(tall, "stream=width,height")
    assert "subtitle" in probe(wide, "stream=codec_type"), "16x9 keeps a soft track"
    assert "subtitle" not in probe(tall, "stream=codec_type"), "9x16 is burned in"
    for f in (wide, tall):
        assert float(probe(f, "format=duration")[0]) == pytest.approx(7.0, abs=0.1)


def test_mux_of_a_format_without_renders_says_which_render_to_run(tmp_path):
    p = make_project(tmp_path)
    r = mux(p, "--format", "9x16")
    assert r.returncode == 1 and "render.sh" in r.stderr and "9x16" in r.stderr
