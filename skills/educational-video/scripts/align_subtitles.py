#!/usr/bin/env python3
"""Build subtitles from per-scene word timestamps, or via forced alignment.

For each scene: prefer audio/scene_<id>.words.json (provider timings). If absent,
run faster-whisper on audio/scene_<id>.wav (installed lazily) to get word timings.
Scene start offsets accumulate from each scene's audio duration. Emits:
  output/subtitles.srt  and  output/subtitles.ass (styled)

Usage: align_subtitles.py <project-dir>
"""
import json
import os
import subprocess
import sys


def audio_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return 0.0


def whisper_words(wav):
    """Force-align via faster-whisper; install on demand."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "faster-whisper"],
                       check=True)
        from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(wav, word_timestamps=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return words


def fmt_srt(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_ass(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def group_lines(words, max_words=7):
    """Group words into caption lines of up to max_words."""
    lines = []
    cur = []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words:
            lines.append(cur); cur = []
    if cur:
        lines.append(cur)
    return [{"start": ln[0]["start"], "end": ln[-1]["end"],
             "text": " ".join(x["word"] for x in ln)} for ln in lines]


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,54,&H00FFFFFF,&H00000000,&H80000000,0,3,1,2,80,80,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    sb = json.load(open(os.path.join(project, "storyboard.json")))
    audio_dir = os.path.join(project, "audio")
    out_dir = os.path.join(project, "output"); os.makedirs(out_dir, exist_ok=True)

    all_lines = []
    offset = 0.0
    for sc in sb["scenes"]:
        sid = sc["id"]
        wav = os.path.join(audio_dir, f"scene_{sid}.wav")
        wjson = os.path.join(audio_dir, f"scene_{sid}.words.json")
        if not os.path.isfile(wav):
            continue
        if os.path.isfile(wjson):
            words = json.load(open(wjson))
        else:
            words = whisper_words(wav)
        for w in words:
            w["start"] += offset; w["end"] += offset
        all_lines.extend(group_lines(words))
        offset += audio_duration(wav)

    # SRT
    srt = os.path.join(out_dir, "subtitles.srt")
    with open(srt, "w") as f:
        for i, ln in enumerate(all_lines, 1):
            f.write(f"{i}\n{fmt_srt(ln['start'])} --> {fmt_srt(ln['end'])}\n{ln['text']}\n\n")
    # ASS
    ass = os.path.join(out_dir, "subtitles.ass")
    with open(ass, "w") as f:
        f.write(ASS_HEADER)
        for ln in all_lines:
            f.write(f"Dialogue: 0,{fmt_ass(ln['start'])},{fmt_ass(ln['end'])},"
                    f"Default,,0,0,0,,{ln['text']}\n")
    print(f"-> {srt}\n-> {ass}  ({len(all_lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
