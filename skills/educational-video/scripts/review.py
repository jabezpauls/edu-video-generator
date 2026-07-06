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
