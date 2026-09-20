#!/usr/bin/env python3
"""Build subtitles from the narration grid.

Uses <project>/grid.json (run grid.py first) so captions sit on exactly the same clock as the
picture and the mix. Without a grid, falls back to per-scene word timings
(audio/scene_<id>.words.json, else forced alignment) and cumulative audio lengths. Emits:
  output/subtitles.srt          soft subtitles (16x9, 1x1, 4x5)
  output/subtitles.ass          styled, 1920x1080
  output/subtitles_9x16.ass     styled for the 1080x1920 frame, burned in by mux.sh: short lines, bigger type, kept
                                clear of the platform UI zones (bottom 20 %, right 12 %)

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
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{size},&H00FFFFFF,&H00000000,&H80000000,{bold},{outline},1,2,{ml},{mr},{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# 1080x1920: type at phone size, text column between the 5 % left margin and the 12 % right UI strip,
# baseline above the bottom 20 % (the captions sit at about 74 % of the height, like the motion engine's)
STYLES = {
    "wide": dict(w=1920, h=1080, size=54, bold=0, outline=3, ml=80, mr=80, mv=70, words=7),
    "tall": dict(w=1080, h=1920, size=68, bold=1, outline=4, ml=54, mr=130, mv=500, words=4),
}


def write_ass(path, lines, style):
    st = STYLES[style]
    with open(path, "w") as f:
        f.write(ASS_HEADER.format(**st))
        for ln in lines:
            f.write(f"Dialogue: 0,{fmt_ass(ln['start'])},{fmt_ass(ln['end'])},"
                    f"Default,,0,0,0,,{ln['text']}\n")


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    sb = json.load(open(os.path.join(project, "storyboard.json")))
    audio_dir = os.path.join(project, "audio")
    out_dir = os.path.join(project, "output"); os.makedirs(out_dir, exist_ok=True)

    grid_path = os.path.join(project, "grid.json")
    all_words = []
    if os.path.isfile(grid_path):
        grid = json.load(open(grid_path))
        for sc in grid["scenes"]:
            all_words.append(sc["words"])
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
            all_words.append(words)
            offset += dur

    # one caption list per scene, so a line never straddles a scene change
    all_lines = [ln for ws in all_words for ln in group_lines(ws)]
    tall_lines = [ln for ws in all_words for ln in group_lines(ws, STYLES["tall"]["words"])]

    # SRT
    srt = os.path.join(out_dir, "subtitles.srt")
    with open(srt, "w") as f:
        for i, ln in enumerate(all_lines, 1):
            f.write(f"{i}\n{fmt_srt(ln['start'])} --> {fmt_srt(ln['end'])}\n{ln['text']}\n\n")
    ass = os.path.join(out_dir, "subtitles.ass")
    write_ass(ass, all_lines, "wide")
    ass_tall = os.path.join(out_dir, "subtitles_9x16.ass")
    write_ass(ass_tall, tall_lines, "tall")
    print(f"-> {srt}\n-> {ass}  ({len(all_lines)} lines)\n-> {ass_tall}  ({len(tall_lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
