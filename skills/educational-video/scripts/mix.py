#!/usr/bin/env python3
"""Mix narration + music bed + sfx -> <project>/audio/mix.wav, mastered.

  narration  each scene's audio placed on the grid clock -> audio/vo.wav
  music      audio/music.wav (music.py), side-chain ducked under the voice
  sfx        audio/sfx.wav (sfx.mjs)
  master     -14 LUFS integrated, true peak <= -1 dBTP, 48 kHz stereo 24-bit

Levels are relative to the narration, in dB (LU): music -17 under speech before ducking,
sfx -9, each moved by the applied preset's music/sfx level_db (a preset with sfx.enabled false
drops the sound effects). Override with flags or a project-level mix.json {"music": -20, "sfx": -8, "vo": 0,
"duck": true, "duck_db": 8}. Only ffmpeg is needed.

Usage: mix.py <project> [--music dB] [--sfx dB] [--vo dB] [--no-duck] [--target LUFS] [--stems]
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import projectcfg  # noqa: E402

SR = 48000
DEFAULTS = {"music": -17.0, "sfx": -9.0, "vo": 0.0, "duck": True, "target": -14.0}
VO_REF = -16.0          # narration is levelled here before mixing, then the master moves it
TP_LIMIT = -1.0         # dBTP
LIMIT_LIN = 0.841       # -1.5 dBFS, applied at 4x oversampling so inter-sample peaks stay < -1 dBTP


def ff(args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg failed:\n" + r.stderr[-2500:])
    return r.stderr


def measure(path):
    """(integrated LUFS, true peak dBTP, loudness range) via ebur128."""
    err = ff(["-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    summ = err[err.rfind("Summary"):]

    def grab(label):
        m = re.search(rf"^\s*{re.escape(label)}\s+(-?[\d.]+|-inf)", summ, re.M)
        return float(m.group(1)) if m else float("-inf")
    return grab("I:"), grab("Peak:"), grab("LRA:")


def vo_graph(placements, duration):
    """ffmpeg graph placing each narration wav at its start time on one mono track.

    placements: [(input_index, start_seconds)]. Returns (filter_complex, output label).
    """
    parts = []
    for idx, start in placements:
        samples = int(round(start * SR))
        parts.append(f"[{idx}:a]aresample={SR},aformat=channel_layouts=mono,adelay={samples}S[v{idx}]")
    labels = "".join(f"[v{idx}]" for idx, _ in placements)
    parts.append(f"{labels}amix=inputs={len(placements)}:normalize=0:duration=longest,"
                 f"apad=whole_dur={duration},atrim=0:{duration}[vo]")
    return ";".join(parts), "[vo]"


def build_vo(project, grid, out):
    files, placements = [], []
    for sc in grid["scenes"]:
        if not sc.get("audio") or sc.get("audio_start") is None:
            continue
        path = os.path.join(project, sc["audio"])
        if os.path.isfile(path):
            placements.append((len(files), sc["audio_start"]))
            files.append(path)
    if not files:
        return False
    graph, label = vo_graph(placements, grid["duration"])
    args = []
    for f in files:
        args += ["-i", f]
    ff([*args, "-filter_complex", graph, "-map", label, "-c:a", "pcm_f32le", out])
    return True


def premix_graph(have, gains, duration, duck, duck_db, summed=True):
    """Graph for the pre-master mix. `have` is the set of stems present, in input order
    vo, music, sfx (only those present). gains in dB per stem.
    Returns (graph, input order, output labels); with summed=False the stems are left separate."""
    order = [k for k in ("vo", "music", "sfx") if k in have]
    chains = []
    for i, k in enumerate(order):
        layout = "pan=stereo|c0=c0|c1=c0" if k == "vo" else "aformat=channel_layouts=stereo"
        chains.append(f"[{i}:a]aresample={SR},{layout},apad,atrim=0:{duration},"
                      f"volume={gains[k]:.3f}dB[{k}]")
    ducked = duck and "vo" in have and "music" in have
    if ducked:
        # Speech peaks sit at about VO_REF + 5 dB on the key; put the threshold duck_db's worth of
        # compression below that. Fast attack so the first syllable is clear, slow release so the
        # bed breathes back in.
        ratio = 4.0
        thr = 10 ** ((VO_REF + 5 - duck_db / (1 - 1 / ratio)) / 20)
        chains.append("[vo]asplit[vo_out][vo_key]")
        chains.append(f"[music][vo_key]sidechaincompress=threshold={thr:.5f}:ratio={ratio}:"
                      "attack=20:release=350:makeup=1[music_out]")
    labels = []
    for k in order:
        labels.append("[vo_out]" if (k == "vo" and ducked) else
                      "[music_out]" if (k == "music" and ducked) else f"[{k}]")
    if summed:
        chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first[mix]")
    return ";".join(chains), order, labels


def master(raw, out, target):
    """Linear gain to the target loudness into a 4x-oversampled limiter; re-measured and nudged."""
    I0, _, _ = measure(raw)
    gain = target - I0
    I = TP = None
    for _ in range(4):
        ff(["-i", raw, "-af",
            f"volume={gain:.2f}dB,aresample={SR * 4},alimiter=limit={LIMIT_LIN}:attack=1:release=40:level=false,"
            f"aresample={SR}", "-ar", str(SR), "-c:a", "pcm_s24le", out])
        I, TP, _ = measure(out)
        if abs(I - target) <= 0.15 and TP <= TP_LIMIT:
            break
        gain += target - I
        if TP > TP_LIMIT:
            gain -= (TP - TP_LIMIT) * 0.5
    return I, TP, gain


def load_levels(project, args):
    lv = dict(DEFAULTS)
    pr = projectcfg.preset(project)
    for k in ("music", "sfx"):
        lv[k] += float((pr.get(k) or {}).get("level_db") or 0)
    if (pr.get("sfx") or {}).get("enabled") is False:
        lv["sfx_off"] = True
    mj = os.path.join(project, "mix.json")
    if os.path.isfile(mj):
        lv.update(json.load(open(mj)))
    for k in ("music", "sfx", "vo", "target"):
        v = getattr(args, k)
        if v is not None:
            lv[k] = v
    if args.no_duck:
        lv["duck"] = False
    lv.setdefault("duck_db", 8.0)
    return lv


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--music", type=float)
    ap.add_argument("--sfx", type=float)
    ap.add_argument("--vo", type=float)
    ap.add_argument("--target", type=float)
    ap.add_argument("--no-duck", action="store_true")
    ap.add_argument("--stems", action="store_true", help="also write the processed stems to audio/stems/")
    a = ap.parse_args(argv)

    project = a.project
    gp = os.path.join(project, "grid.json")
    if not os.path.isfile(gp):
        print("grid.json missing: run grid.py first", file=sys.stderr)
        return 1
    grid = json.load(open(gp))
    dur = grid["duration"]
    lv = load_levels(project, a)
    adir = os.path.join(project, "audio")
    os.makedirs(adir, exist_ok=True)

    stems = {}
    vo_path = os.path.join(adir, "vo.wav")
    if build_vo(project, grid, vo_path):
        stems["vo"] = vo_path
    for k in ("music", "sfx"):
        p = os.path.join(adir, f"{k}.wav")
        if k == "sfx" and lv.get("sfx_off"):
            continue
        if os.path.isfile(p):
            stems[k] = p
    if not stems:
        print("nothing to mix: no narration audio, music.wav or sfx.wav", file=sys.stderr)
        return 1

    # level every stem against the narration (or against a nominal voice level without one)
    ref = VO_REF
    gains = {}
    if "vo" in stems:
        gains["vo"] = VO_REF - measure(stems["vo"])[0] + lv["vo"]
    for k in ("music", "sfx"):
        if k in stems:
            gains[k] = ref + lv[k] - measure(stems[k])[0]
    graph, order, _ = premix_graph(set(stems), gains, dur, lv["duck"], lv["duck_db"])
    raw = os.path.join(adir, "mix_raw.wav")
    inputs = []
    for k in order:
        inputs += ["-i", stems[k]]
    ff([*inputs, "-filter_complex", graph, "-map", "[mix]", "-c:a", "pcm_f32le", raw])
    if a.stems:   # the levelled, ducked stems before mastering, for inspection
        g2, _, labels = premix_graph(set(stems), gains, dur, lv["duck"], lv["duck_db"], summed=False)
        sdir = os.path.join(adir, "stems")
        os.makedirs(sdir, exist_ok=True)
        maps = []
        for k, lab in zip(order, labels):
            maps += ["-map", lab, "-c:a", "pcm_f32le", os.path.join(sdir, f"{k}.wav")]
        ff([*inputs, "-filter_complex", g2, *maps])

    out = os.path.join(adir, "mix.wav")
    I, TP, gain = master(raw, out, lv["target"])
    os.remove(raw)
    report = {"integrated_lufs": round(I, 2), "true_peak_dbtp": round(TP, 2),
              "target_lufs": lv["target"], "duration": dur, "stems": sorted(stems),
              "levels_lu": {k: lv[k] for k in ("vo", "music", "sfx")},
              "ducked": bool(lv["duck"] and "vo" in stems and "music" in stems),
              "master_gain_db": round(gain, 2)}
    with open(os.path.join(adir, "mix_report.json"), "w") as f:
        json.dump(report, f, indent=1)
        f.write("\n")
    print(f"-> {out}  {dur:.1f}s  stems: {', '.join(sorted(stems))}"
          f"{'  (music ducked under narration)' if report['ducked'] else ''}")
    print(f"integrated {I:.1f} LUFS (target {lv['target']:g})   true peak {TP:.1f} dBTP (limit {TP_LIMIT:g})"
          f"   master gain {gain:+.1f} dB")
    if abs(I - lv["target"]) > 0.5 or TP > TP_LIMIT:
        print("WARNING: off target; the limiter is working too hard. Lower the loudest stem "
              "(usually sfx) and re-run.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
