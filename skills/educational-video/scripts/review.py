#!/usr/bin/env python3
"""Build the critique kit for a lesson from its RENDERED mp4s (any engine).

    python3 review.py <round> [--project DIR] [--draft] [--video fmt=path ...]
                      [--mode lesson|short] [--grid FILE] [--cues FILE]

Writes <project>/review/r<round>/ with contact sheets, fast-action strips, phone sheets
(360 px wide, every format), a 9:16 safe-zone sheet and metrics.json. Nothing is judged from
source code or a live preview, so Manim, Remotion and motion-engine projects all work.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FORMATS = {"16x9": (16, 9), "1x1": (1, 1), "4x5": (4, 5), "9x16": (9, 16)}
FONT_CANDIDATES = [
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/noto/NotoSansMono-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/consola.ttf",
    "DejaVuSansMono.ttf",
]


def load_font(size=15):
    """Best monospace font available on this machine; Pillow's built-in as a last resort."""
    for p in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, check=False, **kw)


def probe(path):
    """(width, height, fps, duration_s, has_audio) of a media file."""
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", path],
            text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr.strip()}")
    j = json.loads(r.stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    n, d = (int(x) for x in v["r_frame_rate"].split("/"))
    has_audio = any(s["codec_type"] == "audio" for s in j["streams"])
    return int(v["width"]), int(v["height"]), n / d, float(j["format"]["duration"]), has_audio


def format_of(w, h):
    """Name the delivery format closest to a pixel size by aspect ratio."""
    ar = w / h
    return min(FORMATS, key=lambda f: abs(FORMATS[f][0] / FORMATS[f][1] - ar))


def read_json(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def declared_formats(project):
    for name in ("storyboard.json", "timeline.json"):
        j = read_json(os.path.join(project, name), {})
        if isinstance(j, dict) and j.get("formats"):
            return [f for f in j["formats"] if f in FORMATS]
    return []


def find_videos(project, draft=False, explicit=None):
    """Map format name -> mp4 path for whatever has been rendered.

    Looks in the places each engine writes (renders/, output/) and falls back to naming a lone
    file by its aspect ratio. `explicit` ({fmt: path}) wins over discovery.
    """
    if explicit:
        return {f: os.path.abspath(p) for f, p in explicit.items()}
    pre = "draft_" if draft else ""
    found = {}
    declared = declared_formats(project) or ["16x9"]
    for fmt in list(dict.fromkeys(declared + list(FORMATS))):
        for rel in (f"renders/{pre}{fmt}.mp4", f"output/{pre}final_{fmt}.mp4",
                    f"output/{fmt}/{pre}final.mp4"):
            p = os.path.join(project, rel)
            if os.path.isfile(p):
                found[fmt] = p
                break
    if not found and not draft:
        for rel in ("output/final.mp4", "final.mp4"):
            p = os.path.join(project, rel)
            if os.path.isfile(p):
                w, h, *_ = probe(p)
                found[format_of(w, h)] = p
                break
    return found


# ---------------------------------------------------------------------------------------------
# Single streaming pass over a video: per-frame motion energy, luma stats and edge density.
# ---------------------------------------------------------------------------------------------
ANALYSIS_FPS = 30
ANALYSIS_W = 256
EDGE_T = 48  # gradient magnitude (0-255 scale) that counts as an edge / piece of ink
UNSAFE = {"top": 0.14, "bottom": 0.20, "right": 0.12}  # 9:16 platform UI zones, fraction of frame


def even(n):
    return max(2, int(n) // 2 * 2)


def zone_masks(h, w):
    """Boolean masks over an (h, w) frame for the 9:16 UI zones."""
    top = np.zeros((h, w), bool)
    top[: int(h * UNSAFE["top"])] = True
    bottom = np.zeros((h, w), bool)
    bottom[int(h * (1 - UNSAFE["bottom"])):] = True
    right = np.zeros((h, w), bool)
    right[int(h * UNSAFE["top"]): int(h * (1 - UNSAFE["bottom"])), int(w * (1 - UNSAFE["right"])):] = True
    return {"top": top, "bottom": bottom, "right": right}


def analyze(path, fps=None, zones=False):
    """Stream `path` once at <= 30 fps and return per-frame arrays.

    energy[i]  mean |frame i+1 - frame i| (0-255 scale), so len(energy) == frames - 1
    mean[i], std[i]  luma mean / standard deviation
    ink[i]     fraction of pixels that are edges: a cheap proxy for how much text/linework is up
    zone_ink   {zone: per-frame edge fraction inside each 9:16 UI zone} when zones=True
    """
    w0, h0, nfps, dur, _ = probe(path)
    afps = min(nfps, ANALYSIS_FPS) if fps is None else fps
    w = ANALYSIS_W
    h = even(w * h0 / w0)
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={afps},scale={w}:{h}:flags=area",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        stdout=subprocess.PIPE)
    size = w * h
    masks = zone_masks(h, w) if zones else {}
    mean, std, ink, prev = [], [], [], None
    energy = []
    zi = {k: [] for k in masks}
    while True:
        buf = proc.stdout.read(size * 32)
        if not buf:
            break
        n = len(buf) // size
        if n == 0:
            break
        g = np.frombuffer(buf[: n * size], np.uint8).reshape(n, h, w).astype(np.int16)
        full = g if prev is None else np.concatenate([prev[None], g])
        energy.extend(np.abs(np.diff(full, axis=0)).mean(axis=(1, 2)).tolist())
        prev = g[-1]
        flat = g.reshape(n, -1)
        mean.extend(flat.mean(1).tolist())
        std.extend(flat.std(1).tolist())
        edge = np.zeros(g.shape, bool)
        edge[:, :, 1:] |= np.abs(np.diff(g, axis=2)) > EDGE_T
        edge[:, 1:, :] |= np.abs(np.diff(g, axis=1)) > EDGE_T
        ink.extend(edge.reshape(n, -1).mean(1).tolist())
        for k, m in masks.items():
            zi[k].extend(edge[:, m].mean(1).tolist())
    proc.wait()
    return {"fps": afps, "native_fps": nfps, "duration": dur, "size": (w0, h0),
            "energy": np.array(energy), "mean": np.array(mean), "std": np.array(std),
            "ink": np.array(ink), "zone_ink": {k: np.array(v) for k, v in zi.items()}}
