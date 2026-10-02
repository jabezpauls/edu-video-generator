#!/usr/bin/env python3
"""Synthesize a quiet music bed -> <project>/audio/music.wav (48 kHz stereo, float).

The bed sits under narration. It is not the timing source: visual hits follow the words on
grid.json, the music only follows scene boundaries (a new chord and a soft swell at each one).
No samples, no vocals, seeded and deterministic.

Moods:
  calm     slow warm pad, an occasional high bell      (proofs, derivations, reflective)
  curious  pad plus a sparse mallet motif, light echo  (default for concept explainers)
  upbeat   brighter chords, steady mallet and a soft pulse (intros, shorts, recaps)
  none     write nothing (and remove any old bed)

Usage: music.py <project> [--mood calm|curious|upbeat|none] [--seed N] [--duration S]
Without --mood the applied preset's music mood is used, else upbeat for a short and curious for a lesson.
Duration comes from grid.json unless --duration is given. Needs numpy, scipy, soundfile.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import projectcfg  # noqa: E402

SR = 48000
BED_RMS_DB = -22.0     # loudness of the finished bed; mix.py places it relative to the voice

# name -> (bpm, bar progression, motif density per beat, pulse)
MOODS = {
    "calm": {"bpm": 60, "density": 0.18, "pulse": False, "bright": 0.8,
             "chords": [(0, "maj7"), (9, "min7"), (5, "maj7"), (7, "add9")]},
    "curious": {"bpm": 84, "density": 0.4, "pulse": False, "bright": 1.0,
                "chords": [(2, "min7"), (10, "maj7"), (0, "sus2"), (9, "min7")]},
    "upbeat": {"bpm": 104, "density": 0.75, "pulse": True, "bright": 1.25,
               "chords": [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")]},
}
QUALITY = {"maj": [0, 4, 7, 12], "min": [0, 3, 7, 12], "maj7": [0, 4, 7, 11],
           "min7": [0, 3, 7, 10], "add9": [0, 4, 7, 14], "sus2": [0, 2, 7, 12]}


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def chord_notes(root_pc, quality):
    """(bass midi note, [four chord tones around middle C])."""
    base = 60 + ((root_pc - 60) % 12) - (12 if (root_pc % 12) > 6 else 0)
    return 36 + (root_pc % 12), [base + i for i in QUALITY[quality]]


def plan_segments(boundaries, duration, bar_s):
    """Chord segments: a new one at every scene boundary and every two bars inside long scenes."""
    cuts = sorted({0.0, *[b for b in boundaries if 0 < b < duration]})
    segs = []
    for i, s in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else duration
        step = bar_s * 2
        n = max(1, round((end - s) / step))
        edges = [s + (end - s) * k / n for k in range(n + 1)]
        segs.extend((edges[k], edges[k + 1], k == 0 and i > 0) for k in range(n))
    return segs


def render(duration, boundaries, mood, seed=4242):
    import numpy as np
    from scipy import signal

    cfg = MOODS[mood]
    rng = np.random.default_rng(seed)
    n = int(round(duration * SR))
    beat = 60.0 / cfg["bpm"]
    bar = beat * 4

    def tt(d):
        return np.arange(int(d * SR)) / SR

    def lowpass(x, fc, order=2):
        return signal.sosfilt(signal.butter(order, fc, "low", fs=SR, output="sos"), x, axis=0)

    def band(x, lo, hi):
        return signal.sosfilt(signal.butter(2, [lo, hi], "bandpass", fs=SR, output="sos"), x, axis=0)

    def put(dst, x, t0, gain=1.0, pan=0.0):
        i = int(round(t0 * SR))
        if i >= dst.shape[0] or i + len(x) <= 0:
            return
        if i < 0:
            x, i = x[-i:], 0
        j = min(dst.shape[0], i + len(x))
        dst[i:j, 0] += x[: j - i] * gain * np.sqrt(0.5 * (1 - pan))
        dst[i:j, 1] += x[: j - i] * gain * np.sqrt(0.5 * (1 + pan))

    def pad_voice(f, d, att=0.9, rel=1.4):
        t = tt(d + rel)
        x = (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.0035 * t + 1.1)
             + 0.22 * np.sin(2 * np.pi * 2 * f * t) + 0.08 * np.sin(2 * np.pi * 3 * f * t))
        env = np.minimum(t / att, 1.0) ** 2 * np.clip((d + rel - t) / rel, 0, 1) ** 2
        return x * env

    def mallet(f, d=1.0, bright=1.0):
        t = tt(d)
        idx = 2.0 * bright * np.exp(-t * 26)
        x = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * 4 * f * t))
        x += 0.15 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 12)
        return x * np.minimum(t / 0.002, 1) * np.exp(-t * 5.0)

    def tick(g=1.0):
        t = tt(0.04)
        return band(rng.uniform(-1, 1, len(t)), 5000, 11000) * np.exp(-t * 130) * g

    pads, keys, low = np.zeros((n, 2)), np.zeros((n, 2)), np.zeros((n, 2))
    segs = plan_segments(boundaries, duration, bar)
    prog = cfg["chords"]
    for k, (s0, s1, at_scene) in enumerate(segs):
        root, quality = prog[k % len(prog)]
        bass, tones = chord_notes(root, quality)
        d = s1 - s0
        for j, m in enumerate(tones):
            put(pads, pad_voice(midi(m), d), s0 - 0.25, 0.30, pan=(j - 1.5) * 0.18)
        put(low, pad_voice(midi(bass), d, 1.2, 1.4), s0 - 0.2, 0.45)
        # motif: seeded sparse mallet notes on the beat grid of this segment
        steps = int(d / (beat / 2))
        last = len(tones) // 2
        for st in range(steps):
            on_beat = st % 2 == 0
            p = cfg["density"] * (1.0 if on_beat else 0.55)
            if cfg["bpm"] <= 60 and st % 4:
                continue
            if rng.random() < p:
                last = int(np.clip(last + rng.choice([-1, 0, 1, 2]), 0, len(tones) - 1))
                m = tones[last] + 12
                put(keys, mallet(midi(m), 1.0, cfg["bright"]), s0 + st * beat / 2,
                    0.22 if on_beat else 0.15, pan=float(rng.uniform(-0.5, 0.5)))
        if cfg["pulse"]:
            for b in range(int(d / beat)):
                if b % 4 == 0:
                    put(low, mallet(midi(bass), 0.35, 0.3), s0 + b * beat, 0.5)
                put(keys, tick(0.25 if b % 2 else 0.12), s0 + b * beat + beat / 2, 1.0, pan=0.3)
        if at_scene:   # soft swell into the new scene plus a bell on its first beat
            sw = tt(1.0)
            nz = band(rng.uniform(-1, 1, len(sw)), 500, 4000)
            env = np.where(sw < 0.85, (sw / 0.85) ** 2.2, np.exp(-(sw - 0.85) * 18))
            put(keys, nz * env, s0 - 0.85, 0.22)
            put(keys, mallet(midi(tones[2] + 12), 1.4, 0.8), s0, 0.25)

    # echo on the motif, light room on everything
    delay = int(beat * 0.75 * SR)
    wet = keys.copy()
    for r in range(1, 4):
        if delay * r < n:
            wet[delay * r:] += keys[: n - delay * r] * (0.32 ** r)
    mix = lowpass(pads, 2200) + low + wet
    ir_t = tt(0.9)
    for ch in range(2):
        ir = lowpass(rng.uniform(-1, 1, len(ir_t)) * np.exp(-ir_t * 6), 5000)
        ir /= np.sqrt((ir ** 2).sum())
        mix[:, ch] += 0.18 * signal.oaconvolve(wet[:, ch] + pads[:, ch] * 0.5, ir)[:n]
    mix = signal.sosfilt(signal.butter(2, 40, "high", fs=SR, output="sos"), mix, axis=0)

    fi, fo = int(min(1.0, duration / 4) * SR), int(min(1.6, duration / 3) * SR)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None] ** 2
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    rms = np.sqrt(np.mean(mix ** 2) + 1e-12)
    mix *= 10 ** (BED_RMS_DB / 20) / rms
    peak = np.abs(mix).max()
    if peak > 0.9:
        mix *= 0.9 / peak
    return mix.astype(np.float32)


def boundaries_from_grid(grid):
    return [s["start"] for s in grid["scenes"][1:]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--mood", default=None, choices=[*MOODS, "none"])
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--duration", type=float)
    a = ap.parse_args(argv)

    a.mood = projectcfg.music_mood(a.project, a.mood)
    out = os.path.join(a.project, "audio", "music.wav")
    if a.mood == "none":
        if os.path.isfile(out):
            os.remove(out)
        print("mood none: no music bed")
        return 0
    bounds, duration = [], a.duration
    gp = os.path.join(a.project, "grid.json")
    if os.path.isfile(gp):
        grid = json.load(open(gp))
        bounds = boundaries_from_grid(grid)
        duration = duration or grid["duration"]
    if not duration:
        print("no grid.json and no --duration; run grid.py first", file=sys.stderr)
        return 1
    import soundfile as sf
    os.makedirs(os.path.dirname(out), exist_ok=True)
    mix = render(duration, bounds, a.mood, a.seed)
    sf.write(out, mix, SR, subtype="FLOAT")
    print(f"-> {out}  {duration:.1f}s  mood {a.mood}  {len(bounds)} scene changes  seed {a.seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
