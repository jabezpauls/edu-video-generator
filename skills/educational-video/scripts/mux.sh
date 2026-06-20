#!/usr/bin/env bash
# Assemble the final video: concat scenes, attach narration, normalize loudness,
# soft-mux subtitles. Usage: mux.sh <project-dir> [--burn]
#   --burn  hardcode subtitles into the picture (default: soft-mux .srt)
# Output: <project>/output/final.mp4
set -uo pipefail

PROJECT="${1:?usage: mux.sh <project-dir> [--burn]}"
BURN="${2:-}"
OUT="$PROJECT/output"
TMP="$PROJECT/.videogen/mux"; mkdir -p "$TMP"

# Ordered scene ids from storyboard
mapfile -t IDS < <(python3 -c "import json;print('\n'.join(s['id'] for s in json.load(open('$PROJECT/storyboard.json'))['scenes']))")

# 1. Per-scene: mux narration audio into each scene video (pad video if shorter than audio)
LIST="$TMP/concat.txt"; : > "$LIST"
for id in "${IDS[@]}"; do
  v="$OUT/scene_${id}.mp4"; a="$PROJECT/audio/scene_${id}.wav"
  [[ -f "$v" ]] || { echo "missing scene video: $v" >&2; continue; }
  seg="$TMP/seg_${id}.mp4"
  if [[ -f "$a" ]]; then
    # -shortest would cut; instead pad video to audio length via tpad if needed
    ffmpeg -y -i "$v" -i "$a" \
      -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=0[vv]" \
      -map "[vv]" -map 1:a -af "loudnorm" -c:v libx264 -pix_fmt yuv420p -c:a aac \
      -movflags +faststart "$seg" >/dev/null 2>&1 \
      || ffmpeg -y -i "$v" -i "$a" -map 0:v -map 1:a -c:v libx264 -pix_fmt yuv420p \
           -c:a aac -shortest "$seg" >/dev/null 2>&1
  else
    ffmpeg -y -i "$v" -c:v libx264 -pix_fmt yuv420p "$seg" >/dev/null 2>&1
  fi
  echo "file '$seg'" >> "$LIST"
done

# 2. Concat all segments
CONCAT="$TMP/concat.mp4"
ffmpeg -y -f concat -safe 0 -i "$LIST" -c:v libx264 -pix_fmt yuv420p -c:a aac \
  -movflags +faststart "$CONCAT" >/dev/null 2>&1 \
  || { echo "concat failed" >&2; exit 1; }

# 3. Subtitles
FINAL="$OUT/final.mp4"
SRT="$OUT/subtitles.srt"; ASS="$OUT/subtitles.ass"
if [[ "$BURN" == "--burn" && -f "$ASS" ]]; then
  ffmpeg -y -i "$CONCAT" -vf "subtitles=${ASS}" -c:a copy "$FINAL" >/dev/null 2>&1
elif [[ -f "$SRT" ]]; then
  # soft-mux as mov_text
  ffmpeg -y -i "$CONCAT" -i "$SRT" -c copy -c:s mov_text \
    -metadata:s:s:0 language=eng "$FINAL" >/dev/null 2>&1 \
    || cp "$CONCAT" "$FINAL"
else
  cp "$CONCAT" "$FINAL"
fi

echo "-> $FINAL"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$FINAL" 2>/dev/null \
  | awk '{printf "duration: %.1fs\n",$1}'
