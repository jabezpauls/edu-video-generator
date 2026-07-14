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
CHG_T = 8    # per-pixel luma change that counts as "this pixel moved"
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
    chg[i]     fraction of pixels that moved by more than CHG_T: sees thin, local motion
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
    energy, chg = [], []
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
        d = np.abs(np.diff(full, axis=0))
        energy.extend(d.mean(axis=(1, 2)).tolist())
        chg.extend((d > CHG_T).mean(axis=(1, 2)).tolist())
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
            "energy": np.array(energy), "chg": np.array(chg), "mean": np.array(mean), "std": np.array(std),
            "ink": np.array(ink), "zone_ink": {k: np.array(v) for k, v in zi.items()}}


# ---------------------------------------------------------------------------------------------
# Metrics from the per-frame arrays. Pure functions so they can be tested on tiny clips.
# ---------------------------------------------------------------------------------------------
STILL_SUM = 0.0004  # summed chg over half a second below this: nothing is moving at all
EVENT_CHG = 0.0015  # a visual event moves at least this fraction of the pixels in one frame
BLANK_STD = 4.0     # luma standard deviation below this is a near-uniform (blank) frame


def activity(chg, fps, window=0.5):
    """Moved-pixel fraction summed over a centred half-second window: tolerant of slow drawing."""
    k = max(1, int(round(window * fps)))
    return np.convolve(chg, np.ones(k), "same")


def longest_static(chg, fps):
    """Longest stretch in which (almost) no pixel changes, in seconds."""
    still = activity(chg, fps) < STILL_SUM
    run = best = end = 0
    for i, s in enumerate(still):
        run = run + 1 if s else 0
        if run > best:
            best, end = run, i
    return {"seconds": round(best / fps, 2), "from_s": round((end - best + 1) / fps, 2) if best else 0.0}


def visual_events(chg, fps, min_sep=0.25):
    """Times (s) where something new starts: a sharp burst of change, or motion resuming after a hold."""
    if len(chg) == 0:
        return []
    sm = np.convolve(chg, np.ones(3) / 3, "same")
    thr = max(EVENT_CHG, 2.5 * float(np.median(sm)))
    marks = []
    for i in range(len(sm)):
        left = sm[i - 1] if i else -1
        right = sm[i + 1] if i + 1 < len(sm) else -1
        if sm[i] >= thr and sm[i] >= left and sm[i] > right:
            j = i  # report the onset of the burst, not its peak
            while j > 0 and sm[j - 1] >= 0.5 * sm[i] and i - j < int(0.5 * fps):
                j -= 1
            marks.append(j)
    act = activity(chg, fps) >= STILL_SUM
    marks += [i for i in range(1, len(act)) if act[i] and not act[i - 1]]  # motion resumes after a hold
    out = []
    for m in sorted(marks):
        if out and (m - out[-1]) / fps < min_sep:
            continue
        out.append(m)
    return [round((m + 1) / fps, 3) for m in out]


def max_gap(events, duration):
    ts = np.r_[0.0, events, duration]
    gaps = np.diff(ts)
    i = int(np.argmax(gaps))
    return {"seconds": round(float(gaps[i]), 2), "from_s": round(float(ts[i]), 2)}


def blank_runs(std, mean, fps, thr=BLANK_STD):
    runs = []
    for i in np.where(std < thr)[0]:
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = int(i)
        else:
            runs.append([int(i), int(i)])
    n = len(std)
    return [{"from_s": round(a / fps, 3), "frames": b - a + 1, "seconds": round((b - a + 1) / fps, 3),
             "mean_luma": int(mean[a]),
             "where": "start" if a == 0 else "end" if b == n - 1 else "mid"} for a, b in runs]


DENSE_INK = 0.06  # edge fraction above which a frame is crowded (a full page of text or code)


def hook_metrics(ink, std, chg, fps, window=3.0):
    """What a viewer gets in the first seconds: when content first appears and how much moves."""
    n = len(std)
    first = next((i for i in range(n) if std[i] >= BLANK_STD and ink[i] >= 0.002), None)
    k = max(1, int(window * fps))
    return {
        "frame0_blank": bool(n and std[0] < BLANK_STD),
        "first_content_s": None if first is None else round(first / fps, 2),
        "motion_in_first_3s": round(float(chg[:k].sum()) * 100, 2),  # frame-fractions summed, in %
        "events_in_first_3s": len(visual_events(chg[:k], fps)),
    }


def density_metrics(ink, fps):
    """Text/linework load per frame (edge fraction). Flags stretches that are crowded."""
    if len(ink) == 0:
        return {"mean": 0.0, "max": 0.0, "max_at_s": 0.0, "crowded_seconds": 0.0, "crowded_from_s": None}
    crowded = ink > DENSE_INK
    run = best = end = 0
    for i, c in enumerate(crowded):
        run = run + 1 if c else 0
        if run > best:
            best, end = run, i
    return {"mean": round(float(ink.mean()), 4), "max": round(float(ink.max()), 4),
            "max_at_s": round(int(ink.argmax()) / fps, 2),
            "crowded_seconds": round(float(crowded.sum()) / fps, 2),
            "longest_crowded_s": round(best / fps, 2),
            "crowded_from_s": round((end - best + 1) / fps, 2) if best else None,
            "rule": f"edge fraction > {DENSE_INK} reads as a wall of text/linework"}


# ---------------------------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------------------------
def grab(path, w, h, fps=None, start=None, count=None):
    """RGB frames as an (n, h, w, 3) array: sampled at `fps` from `start`, at most `count`."""
    cmd = ["ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", path, "-vf", (f"fps={fps}," if fps else "") + f"scale={w}:{h}:flags=area"]
    if count:
        cmd += ["-frames:v", str(count)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = run(cmd).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def tile(ims, cols, labels, out, pad=6, lab=22, bg=(20, 20, 20), font=None):
    font = font or load_font(15)
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + pad) + pad, rows * (h + lab + pad) + pad), bg)
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(zip(ims, labels)):
        x = pad + (i % cols) * (w + pad)
        y = pad + (i // cols) * (h + lab + pad)
        sheet.paste(im, (x, y + lab))
        d.text((x + 2, y + 3), label, fill=(235, 235, 235), font=font)
    sheet.save(out, quality=88)
    return out


def sheet_paths(out_dir, base, n_sheets):
    return [os.path.join(out_dir, f"{base}.jpg" if i == 0 else f"{base}_{i + 1}.jpg")
            for i in range(n_sheets)]


def sampled_sheets(path, out_dir, base, tw, th, cols, per_sheet, base_fps, max_sheets, dur, zone_fn=None):
    """Sample a render evenly and tile it into at most `max_sheets` sheets.

    Short videos get `base_fps` frames per second; long ones are thinned so a whole lesson
    still fits in a handful of images. Returns (paths, seconds_between_frames).
    """
    step = max(1.0 / base_fps, dur / (per_sheet * max_sheets))
    frames = grab(path, tw, th, fps=1.0 / step)
    chunks = [list(range(i, min(i + per_sheet, len(frames)))) for i in range(0, len(frames), per_sheet)]
    paths = []
    for p, idx in zip(sheet_paths(out_dir, base, len(chunks)), chunks):
        ims = [Image.fromarray(frames[i]) for i in idx]
        if zone_fn:
            ims = [zone_fn(im) for im in ims]
        tile(ims, cols, [f"{i * step:.1f}s" for i in idx], p)
        paths.append(p)
    return paths, step


def shade_unsafe(im):
    """Overlay the 9:16 platform UI zones (top 14 %, bottom 20 %, right 12 %) in translucent red."""
    im = im.convert("RGBA")
    w, h = im.size
    o = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(o)
    red = (255, 0, 80, 80)
    d.rectangle([0, 0, w, int(h * UNSAFE["top"])], fill=red)
    d.rectangle([0, int(h * (1 - UNSAFE["bottom"])), w, h], fill=red)
    d.rectangle([int(w * (1 - UNSAFE["right"])), int(h * UNSAFE["top"]), w,
                 int(h * (1 - UNSAFE["bottom"]))], fill=red)
    return Image.alpha_composite(im, o).convert("RGB")


def fast_action_strips(path, out_dir, energy, fps, dur, w0, h0, n=2, length=12):
    """12 consecutive frames around each of the n fastest moments: pops, overlaps, bad arcs."""
    if len(energy) < length:
        return [], []
    win = np.convolve(energy, np.ones(length), "valid")
    peaks = []
    for i in np.argsort(win)[::-1]:
        if all(abs(int(i) - p) > int(1.0 * fps) for p in peaks):
            peaks.append(int(i))
        if len(peaks) == 5:
            break
    sw = 640 if w0 >= h0 else 360
    sh = even(sw * h0 / w0)
    paths = []
    for k, c in enumerate(peaks[:n]):
        start = max(0.0, min(c, len(energy) - length) / fps)
        fr = grab(path, sw, sh, fps=fps, start=start, count=length)
        if not len(fr):
            continue
        p = os.path.join(out_dir, "strip_fast.jpg" if k == 0 else f"strip_fast{k + 1}.jpg")
        tile([Image.fromarray(x) for x in fr], 6, [f"{start + i / fps:.2f}s" for i in range(len(fr))], p)
        paths.append(p)
    return paths, [round(p / fps, 2) for p in peaks]


ZONE_INK = 0.012  # edge fraction inside a UI zone that means "something is drawn there"


def safe_zone_metrics(zone_ink, fps):
    """Per-zone: how long content sits inside the 9:16 platform UI zones, and when it starts."""
    out = {}
    for z, arr in zone_ink.items():
        on = arr > ZONE_INK
        run = best = end = 0
        for i, c in enumerate(on):
            run = run + 1 if c else 0
            if run > best:
                best, end = run, i
        out[z] = {"seconds_with_content": round(float(on.sum()) / fps, 2),
                  "longest_run_s": round(best / fps, 2),
                  "longest_run_from_s": round((end - best + 1) / fps, 2) if best else None,
                  "max_edge_fraction": round(float(arr.max()), 4) if len(arr) else 0.0}
    return out


def loudness(path):
    """Integrated loudness (LUFS) and true peak (dBTP), or None when there is no audio."""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true",
             "-f", "null", "-"], text=True)
    summ = r.stderr[r.stderr.rfind("Summary"):]
    vals = {}
    for line in summ.splitlines():
        s = line.strip()
        if s.startswith("I:"):
            vals["lufs"] = float(s.split()[1])
        elif s.startswith("Peak:"):
            vals["true_peak_dbtp"] = float(s.split()[1])
    return vals or None


def dead_air(path, noise_db=-45, min_s=0.8):
    """Silent stretches in the audio track: [{from_s, seconds}]; longest first."""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
             f"silencedetect=noise={noise_db}dB:d={min_s}", "-f", "null", "-"], text=True)
    runs, start = [], None
    for line in r.stderr.splitlines():
        if "silence_start:" in line:
            start = float(line.split("silence_start:")[1].split()[0])
        elif "silence_end:" in line and start is not None:
            end = float(line.split("silence_end:")[1].split()[0])
            runs.append({"from_s": round(max(start, 0.0), 2), "seconds": round(end - max(start, 0.0), 2)})
            start = None
    if start is not None:  # silence runs to the end of the file
        total = probe(path)[3]
        runs.append({"from_s": round(start, 2), "seconds": round(total - start, 2)})
    return sorted(runs, key=lambda x: -x["seconds"])


# ---------------------------------------------------------------------------------------------
# Cue sync: do things appear when they are said? Optional: needs a cue file, degrades without.
# ---------------------------------------------------------------------------------------------
TIME_KEYS = ("t", "time", "at", "start", "s")
HIT_IGNORE = ("whoosh", "riser", "tick", "bed", "swell")  # sfx that build into, or sit under, a hit


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def normalize_cues(raw):
    """Accept the cue shapes a project may carry and return [{name, t, type?, what?}].

    {"s03.derivative": 12.3}  |  {"cues": {...}}  |  {"cues": [{"name"|"what", "t", "type"}]}  |  [..]
    """
    if isinstance(raw, dict) and "cues" in raw:
        raw = raw["cues"]
    out = []
    if isinstance(raw, dict):
        for name, v in raw.items():
            t = _num(v)
            if t is None and isinstance(v, dict):
                t = next((_num(v[k]) for k in TIME_KEYS if k in v and _num(v[k]) is not None), None)
            if t is not None:
                out.append({"name": str(name), "t": t,
                            **({"type": v["type"]} if isinstance(v, dict) and "type" in v else {})})
    elif isinstance(raw, list):
        for c in raw:
            if isinstance(c, dict):
                t = next((_num(c[k]) for k in TIME_KEYS if k in c and _num(c[k]) is not None), None)
                if t is None:
                    continue
                e = {"name": str(c.get("name") or c.get("cue") or c.get("what") or f"t{t:g}"), "t": t}
                if "type" in c:
                    e["type"] = str(c["type"])
                if "what" in c:
                    e["what"] = str(c["what"])
                out.append(e)
            elif isinstance(c, (list, tuple)) and len(c) == 2 and _num(c[1]) is not None:
                out.append({"name": str(c[0]), "t": float(c[1])})
    return sorted(out, key=lambda c: c["t"])


def load_cues(project, grid=None, cues=None):
    """Cue list and where it came from, or ([], None) when the project has none.

    cues.json is preferred (it is what the film was built from); grid.json is the fallback.
    """
    cands = [cues] if cues else [os.path.join(project, "cues.json"), os.path.join(project, "grid.json"),
                                 os.path.join(project, "audio", "grid.json")]
    if grid and not cues:
        cands = [grid] + cands
    for p in cands:
        if p and os.path.isfile(p):
            got = normalize_cues(read_json(p, None))
            if got:
                return got, os.path.relpath(p, project) if os.path.isabs(p) else p
    return [], None


def onset_near(chg, fps, t, window=0.5):
    """Visual onset near time t: first frame of the nearest burst, i.e. the first frame reaching
    50 % of that burst's peak. None when nothing moves enough nearby to count as an event."""
    lo = max(0, int(round((t - window) * fps)))
    hi = min(len(chg), int(round((t + window) * fps)) + 1)
    if hi - lo < 2:
        return None
    seg = chg[lo:hi]
    peak = float(seg.max())
    if peak < EVENT_CHG:
        return None
    cand = np.where(seg >= 0.5 * peak)[0]
    near = int(cand[np.argmin(np.abs((lo + cand + 1) / fps - t))])
    j = near
    while j > 0 and seg[j - 1] >= 0.5 * peak:
        j -= 1
    return (lo + j + 1) / fps


def sync_metrics(cues, chg, fps, duration, tolerance_ms=80):
    """Visual onset minus cue time for each cue that has a visual event close by.

    Positive = picture late. Cues without any visual event nearby are counted, not scored, since
    not every spoken word is meant to trigger something.
    """
    rows, none = [], 0
    for c in cues:
        if c["t"] >= duration - 0.05 or c.get("type") in HIT_IGNORE:
            continue
        v = onset_near(chg, fps, c["t"])
        if v is None:
            none += 1
            continue
        rows.append({"cue": c["name"], "t": round(c["t"], 3), "visual_minus_cue_ms": round((v - c["t"]) * 1000)})
    d = np.array([r["visual_minus_cue_ms"] for r in rows], float)
    res = {"cues_total": len(cues), "cues_with_visual": len(rows), "cues_without_visual": none,
           "tolerance_ms": tolerance_ms, "cues": rows[:200]}
    if len(d):
        res.update({"within_tolerance": f"{int((np.abs(d) <= tolerance_ms).sum())}/{len(d)}",
                    "median_ms": round(float(np.median(d))), "mean_abs_ms": round(float(np.abs(d).mean()), 1),
                    "worst_ms": round(float(d[np.abs(d).argmax()]))})
    res["note"] = ("positive = picture late, negative = picture early; resolution is one analysis frame "
                   f"({1000 / fps:.0f} ms). Visuals should land on the word, +-{tolerance_ms} ms.")
    return res


# ---------------------------------------------------------------------------------------------
# Thresholds and flags. Looser than a promo reel: a lesson may hold while narration explains a
# displayed result. Each flag names the critic criterion it bears on and the cap it implies.
# ---------------------------------------------------------------------------------------------
THRESHOLDS = {
    "lesson": {"static_s": (6, 10), "gap_s": (6, 10), "first_content_s": (1.0, 2.5),
               "dead_air_s": (2.5, 5.0), "crowded_s": (8, 15), "mid_blank_s": (0.3, 1.0)},
    "short": {"static_s": (3, 5), "gap_s": (4, 6), "first_content_s": (0.5, 1.5),
              "dead_air_s": (1.5, 3.0), "crowded_s": (4, 8), "mid_blank_s": (0.2, 0.5)},
}
LUFS_TARGET, LUFS_WARN, LUFS_FAIL, TP_MAX = -14.0, 1.5, 3.0, -1.0
SYNC_WARN_MS, SYNC_FAIL_MS = 80, 150
ZONE_WARN_S = 1.0


def level(value, bounds):
    warn, fail = bounds
    return "fail" if value > fail else "warn" if value > warn else None


def build_flags(M, mode):
    T = THRESHOLDS[mode]
    flags = []

    def add(lv, criterion, metric, msg, cap=None):
        if lv:
            flags.append({"level": lv, "criterion": criterion, "metric": metric, "message": msg,
                          **({"suggested_cap": cap} if cap else {})})

    h = M["hook"]
    if h["frame0_blank"]:
        add("fail", "Hook", "hook.frame0_blank", "frame 0 is near-blank", 6)
    if h["first_content_s"] is None:
        add("fail", "Hook", "hook.first_content_s", "no content ever appears", 6)
    else:
        add(level(h["first_content_s"], T["first_content_s"]), "Hook", "hook.first_content_s",
            f"first content only at {h['first_content_s']} s")
    s = M["longest_static"]
    add(level(s["seconds"], T["static_s"]), "Pacing", "longest_static",
        f"nothing moves for {s['seconds']} s from {s['from_s']} s", 7)
    g = M["max_gap_between_visual_events"]
    add(level(g["seconds"], T["gap_s"]), "Pacing", "max_gap_between_visual_events",
        f"{g['seconds']} s without a new visual event from {g['from_s']} s", 7)
    for b in M["near_blank_frames"]:
        if b["where"] == "mid":
            add(level(b["seconds"], T["mid_blank_s"]), "Polish", "near_blank_frames",
                f"blank frame(s) mid-film at {b['from_s']} s ({b['seconds']} s)", 7)
    d = M["text_density"]
    add(level(d.get("longest_crowded_s", 0), T["crowded_s"]), "Clarity", "text_density",
        f"crowded screen for {d.get('longest_crowded_s')} s from {d.get('crowded_from_s')} s")
    ld = M.get("loudness")
    if ld and "lufs" in ld:
        off = abs(ld["lufs"] - LUFS_TARGET)
        add("fail" if off > LUFS_FAIL else "warn" if off > LUFS_WARN else None, "Polish",
            "loudness.lufs", f"integrated {ld['lufs']} LUFS, target {LUFS_TARGET:g}", 6)
        if ld.get("true_peak_dbtp", -99) > TP_MAX:
            add("warn", "Polish", "loudness.true_peak_dbtp", f"true peak {ld['true_peak_dbtp']} dBTP > {TP_MAX:g}", 6)
    runs = M.get("dead_air") or []
    if runs:
        add(level(runs[0]["seconds"], T["dead_air_s"]), "Pacing", "dead_air",
            f"{runs[0]['seconds']} s of silence from {runs[0]['from_s']} s")
    sy = M.get("sync")
    if sy and "mean_abs_ms" in sy:
        worst = max(abs(sy["median_ms"]), sy["mean_abs_ms"])
        add("fail" if worst > SYNC_FAIL_MS else "warn" if worst > SYNC_WARN_MS else None,
            "Narration sync", "sync", f"median {sy['median_ms']} ms, mean |offset| {sy['mean_abs_ms']} ms "
            f"over {sy['cues_with_visual']} cues (positive = picture late)", 6)
    for z, v in (M.get("safe_zone") or {}).items():
        if v["longest_run_s"] > ZONE_WARN_S:
            add("warn", "Readability", f"safe_zone.{z}", f"content in the 9:16 {z} UI zone for "
                f"{v['longest_run_s']} s from {v['longest_run_from_s']} s", 7)
    durs = {f: i["duration"] for f, i in M["formats"].items()}
    if durs and max(durs.values()) - min(durs.values()) > 0.5:
        add("warn", "Polish", "formats.duration", f"format durations differ: {durs}")
    for f, i in M["formats"].items():
        if f in FORMATS and abs(i["size"][0] / i["size"][1] - FORMATS[f][0] / FORMATS[f][1]) > 0.02:
            add("warn", "Polish", f"formats.{f}", f"{f} render is {i['size'][0]}x{i['size'][1]}")
        if not i["has_audio"]:
            add("warn", "Polish", f"formats.{f}", f"{f} render has no audio track")
    return flags


# ---------------------------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------------------------
def pick_primary(videos, declared):
    for f in declared + ["16x9"]:
        if f in videos:
            return f
    return next(iter(videos))


def ensure_review_log(project):
    """Seed docs/review_log.md from the skill's template the first time a round runs."""
    dest = os.path.join(project, "docs", "review_log.md")
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "review_log.md")
    if os.path.exists(dest) or not os.path.isfile(tpl):
        return None
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(tpl) as src, open(dest, "w") as out:
        out.write(src.read())
    return dest


def parse_args(argv):
    import argparse
    ap = argparse.ArgumentParser(description="Build the lesson critique kit from rendered mp4s.")
    ap.add_argument("round", nargs="?", default="1")
    ap.add_argument("--project", default=".", help="project root (default: cwd)")
    ap.add_argument("--draft", action="store_true", help="read draft_<fmt>.mp4 renders")
    ap.add_argument("--video", action="append", default=[], metavar="FMT=PATH",
                    help="use this mp4 for a format instead of discovering one (repeatable)")
    ap.add_argument("--mode", choices=sorted(THRESHOLDS), help="threshold set (default: storyboard mode)")
    ap.add_argument("--grid", help="grid.json with named cues (default: auto)")
    ap.add_argument("--cues", help="cues.json mapping cues to seconds (default: auto)")
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    project = os.path.abspath(a.project)
    explicit = {}
    for spec in a.video:
        fmt, _, p = spec.partition("=")
        if not p or not os.path.isfile(p):
            raise SystemExit(f"--video wants FMT=PATH to an existing file, got {spec!r}")
        explicit[fmt if fmt in FORMATS else format_of(*probe(p)[:2])] = p
    videos = find_videos(project, a.draft, explicit)
    if not videos:
        raise SystemExit("no renders found (looked in renders/ and output/). Render first, or pass --video FMT=PATH")
    declared = declared_formats(project)
    mode = a.mode or (read_json(os.path.join(project, "storyboard.json"), {}) or {}).get("mode") or "lesson"
    mode = mode if mode in THRESHOLDS else "lesson"
    out = os.path.join(project, "review", f"r{a.round}")
    os.makedirs(out, exist_ok=True)

    info = {}
    for f, p in videos.items():
        w, h, fps, dur, aud = probe(p)
        info[f] = {"path": os.path.relpath(p, project), "size": [w, h], "fps": round(fps, 3),
                   "duration": round(dur, 3), "has_audio": aud}
    P = pick_primary(videos, declared)
    W0, H0 = info[P]["size"]
    an = analyze(videos[P])
    fps, dur = an["fps"], info[P]["duration"]
    wide = W0 >= H0

    M = {"round": a.round, "mode": mode, "primary_format": P, "source": info[P]["path"],
         "analysis_fps": round(fps, 3), "duration": dur, "formats": info}
    # contact sheet(s) of the primary format, thinned for long lessons
    tw = 440 if wide else 240
    sheets, step = sampled_sheets(videos[P], out, "contact", tw, even(tw * H0 / W0), 4 if wide else 8,
                                  20 if wide else 24, 2, 4, dur)
    M["contact_sheets"] = {"files": [os.path.basename(s) for s in sheets], "seconds_per_frame": round(step, 2)}
    strips, peaks = fast_action_strips(videos[P], out, an["energy"], fps, dur, W0, H0)
    M["motion_peaks_s"] = peaks
    M["longest_static"] = longest_static(an["chg"], fps)
    events = visual_events(an["chg"], fps)
    M["visual_events"] = len(events)
    M["max_gap_between_visual_events"] = {**max_gap(events, dur), "rule": "lesson: something new every ~3-6 s"}
    M["near_blank_frames"] = blank_runs(an["std"], an["mean"], fps)
    M["hook"] = hook_metrics(an["ink"], an["std"], an["chg"], fps)
    M["text_density"] = density_metrics(an["ink"], fps)

    # phone sheets, every format; 9:16 also gets the safe-zone sheet and zone metrics
    M["phone_sheets"] = {}
    for f, p in videos.items():
        w, h = info[f]["size"]
        ph = even(360 * h / w)
        tall = h / w > 1.5
        cols, per = (5, 15) if tall else (4, 12 if h > w else 16)
        files, st = sampled_sheets(p, out, f"phone_{f}", 360, ph, cols, per, 1, 4, info[f]["duration"])
        M["phone_sheets"][f] = {"files": [os.path.basename(x) for x in files], "seconds_per_frame": round(st, 2)}
        if f == "9x16":
            files, _ = sampled_sheets(p, out, "safe_9x16", 360, ph, cols, per, 1, 4, info[f]["duration"],
                                      zone_fn=shade_unsafe)
            M["safe_sheets"] = [os.path.basename(x) for x in files]
            z = analyze(p, zones=True)
            M["safe_zone"] = safe_zone_metrics(z["zone_ink"], z["fps"])

    M["loudness"] = loudness(videos[P]) or "no audio"
    if not isinstance(M["loudness"], dict):
        M["loudness"] = None
    M["dead_air"] = dead_air(videos[P])[:5] if info[P]["has_audio"] else []
    cues, src = load_cues(project, a.grid, a.cues)
    if cues:
        M["sync"] = {"source": src, **sync_metrics(cues, an["chg"], fps, dur)}
    else:
        M["sync"] = None
        M["sync_note"] = "no cues.json/grid.json found: narration sync must be judged by eye from the sheets"
    M["thresholds"] = {"mode": mode, **{k: list(v) for k, v in THRESHOLDS[mode].items()}}
    M["flags"] = build_flags(M, mode)

    with open(os.path.join(out, "metrics.json"), "w") as fh:
        json.dump(M, fh, indent=1)
    log = ensure_review_log(project)
    brief = {k: M[k] for k in ("mode", "primary_format", "duration", "longest_static",
                               "max_gap_between_visual_events", "hook", "loudness")}
    print(json.dumps(brief, indent=1))
    if M["sync"] and "within_tolerance" in M["sync"]:
        print("sync:", M["sync"]["within_tolerance"], f"within {SYNC_WARN_MS} ms, median", M["sync"]["median_ms"], "ms")
    for fl in M["flags"]:
        print(f"[{fl['level']}] {fl['criterion']}: {fl['message']}")
    print(f"wrote {os.path.relpath(out)}/: " + " ".join(sorted(os.listdir(out))))
    if log:
        print("created", os.path.relpath(log, project))
    return M


if __name__ == "__main__":
    main()
