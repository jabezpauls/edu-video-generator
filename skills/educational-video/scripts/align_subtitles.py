#!/usr/bin/env python3
"""Build subtitles from the narration grid.

Uses <project>/grid.json (run grid.py first) so captions sit on exactly the same clock as the
picture and the mix. Without a grid, falls back to per-scene word timings
(audio/scene_<id>.words.json, else forced alignment) and cumulative audio lengths. Emits:
  output/subtitles.srt  and  output/subtitles.ass (styled)

Usage: align_subtitles.py <project-dir>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wordtimes as wt  # noqa: E402


def fmt_srt(t):
    total_ms = max(0, round(t * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    sec, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def fmt_ass(t):
    total_cs = max(0, round(t * 100))
    h, rem = divmod(total_cs, 360_000)
    m, rem = divmod(rem, 6000)
    sec, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{sec:02d}.{cs:02d}"


def group_lines(words, max_words=7):
    """Group words into caption lines of up to max_words."""
    lines = []
    cur = []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or (len(cur) >= 3 and wt.ends_sentence(w["word"])):
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

    grid_path = os.path.join(project, "grid.json")
    all_lines = []
    if os.path.isfile(grid_path):
        grid = json.load(open(grid_path))
        for sc in grid["scenes"]:
            all_lines.extend(group_lines(sc["words"]))
    else:
        offset = 0.0
        for sc in sb["scenes"]:
            sid = sc["id"]
            wav = os.path.join(audio_dir, f"scene_{sid}.wav")
            if not os.path.isfile(wav):
                continue
            words, _, dur = wt.scene_words(project, sid, sc.get("narration", ""))
            for w in words:
                w["start"] += offset; w["end"] += offset
            all_lines.extend(group_lines(words))
            offset += dur

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
