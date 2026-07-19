"""Tiny synthetic videos for the critic tests, generated with ffmpeg (no fonts, no assets)."""
import shutil
import subprocess

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def make_video(path, size="320x180", fps=10, dur=2.0, bg="black", boxes=(), tones=None, rate=48000):
    """Write an mp4.

    boxes: dicts with x, y, w, h, color, t0 (appears), t1 (disappears, optional),
           dx (pixels to slide over `slide` seconds after t0).
    tones: list of (t0, t1, freq, amp) bursts; None for a silent-free (video-only) file.
    """
    inputs = ["-f", "lavfi", "-i", f"color=c={bg}:s={size}:r={fps}:d={dur}"]
    chain, last = [], "[0:v]"
    for i, b in enumerate(boxes):
        inputs += ["-f", "lavfi", "-i",
                   f"color=c={b.get('color', 'white')}:s={b['w']}x{b['h']}:r={fps}:d={dur}"]
        t0, t1 = b.get("t0", 0), b.get("t1", dur + 1)
        slide = b.get("slide", 0.3)
        xe = f"{b['x']}+{b.get('dx', 0)}*min(1\\,max(0\\,(t-{t0})/{slide}))"
        chain.append(f"{last}[{i + 1}:v]overlay=x='{xe}':y={b['y']}:eval=frame:"
                     f"enable='between(t\\,{t0}\\,{t1})'[v{i}]")
        last = f"[v{i}]"
    cmd = ["ffmpeg", "-v", "error", "-y"] + inputs
    if tones is not None:
        expr = "+".join(f"{a}*sin(2*PI*{f}*t)*between(t\\,{t0}\\,{t1})" for t0, t1, f, a in tones) or "0"
        cmd += ["-f", "lavfi", "-i", f"aevalsrc='{expr}':s={rate}:d={dur}"]
    if chain:
        cmd += ["-filter_complex", ";".join(chain), "-map", last]
    else:
        cmd += ["-map", "0:v"]
    if tones is not None:
        cmd += ["-map", f"{len(boxes) + 1}:a", "-c:a", "aac", "-ar", str(rate)]
    cmd += ["-pix_fmt", "yuv420p", "-t", str(dur), str(path)]
    subprocess.run(cmd, check=True)
    return path
