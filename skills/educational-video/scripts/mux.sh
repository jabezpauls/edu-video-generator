#!/usr/bin/env bash
# Assemble the final video from per-scene renders (Manim / Remotion) and the mastered mix.
#
# Usage: mux.sh <project-dir> [--burn] [--remix]
#   --burn   hardcode subtitles into the picture (default: soft-mux .srt)
#   --remix  rebuild audio/mix.wav even if it is up to date
#
# Needs grid.json (scripts/grid.py). Each scene video is conformed to its grid duration (the
# last frame is held if the render is short, extra frames are trimmed), the scenes are
# concatenated, and audio/mix.wav (narration + bed + sfx at -14 LUFS, see mix.py) is muxed in.
# The mix is rebuilt first when it is missing or older than its inputs.
# Output: <project>/output/final.mp4
set -uo pipefail

PROJECT=""; BURN=""; REMIX=""
for arg in "$@"; do
  case "$arg" in
    --burn) BURN=1;;
    --remix) REMIX=1;;
    -*) echo "unknown option: $arg" >&2; exit 2;;
    *) PROJECT="$arg";;
  esac
done
[[ -n "$PROJECT" ]] || { echo "usage: mux.sh <project-dir> [--burn] [--remix]" >&2; exit 2; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$PROJECT/output"; GRID="$PROJECT/grid.json"; MIX="$PROJECT/audio/mix.wav"
TMP="$PROJECT/.videogen/mux"; mkdir -p "$TMP" "$OUT"
PY="$PROJECT/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3

[[ -f "$GRID" ]] || { echo "grid.json missing: run scripts/grid.py $PROJECT first" >&2; exit 1; }

# scene id, grid duration and fps, one per line: "<id> <seconds>", first line "fps <n>"
mapfile -t ROWS < <("$PY" -c "
import json,sys
g=json.load(open(sys.argv[1]))
print('fps', g.get('fps') or 30)
for s in g['scenes']: print(s['id'], s['duration'])" "$GRID")
FPS="${ROWS[0]#fps }"; ROWS=("${ROWS[@]:1}")

probe() { ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$1" 2>/dev/null; }

# 1. Conform each scene video to its grid duration (video only; the mix carries all audio)
LIST="$TMP/concat.txt"; : > "$LIST"
for row in "${ROWS[@]}"; do
  id="${row%% *}"; want="${row#* }"
  v="$OUT/scene_${id}.mp4"; seg="$TMP/seg_${id}.mp4"
  [[ -f "$v" ]] || { echo "missing scene video: $v" >&2; exit 1; }
  have="$(probe "$v")"
  delta="$(awk -v h="$have" -v w="$want" 'BEGIN{printf "%.3f", w-h}')"
  filt="fps=${FPS}"
  if awk -v d="$delta" 'BEGIN{exit !(d>0.02)}'; then
    filt="${filt},tpad=stop_mode=clone:stop_duration=${delta}"
    awk -v d="$delta" 'BEGIN{exit !(d>0.25)}' \
      && echo "warning: scene $id render is ${delta}s shorter than its narration slot (last frame held); extend the animation" >&2
  elif awk -v d="$delta" 'BEGIN{exit !(d<-0.1)}'; then
    echo "warning: scene $id render is ${delta#-}s longer than its slot (trimmed); shorten the animation" >&2
  fi
  ffmpeg -y -i "$v" -an -vf "$filt" -t "$want" -c:v libx264 -preset medium -crf 18 \
    -pix_fmt yuv420p "$seg" >/dev/null 2>&1 \
    || { echo "could not conform scene $id" >&2; exit 1; }
  segpath="$(cd "$TMP" && pwd)/seg_${id}.mp4"
  echo "file '${segpath//\'/\'\\\'\'}'" >> "$LIST"   # concat-demuxer quoting for paths with quotes
done

# 2. Concat the conformed scenes (identical encodes, so stream copy)
CONCAT="$TMP/concat.mp4"
ffmpeg -y -f concat -safe 0 -i "$LIST" -c copy "$CONCAT" >/dev/null 2>&1 \
  || { echo "concat failed" >&2; exit 1; }
DUR="$(probe "$CONCAT")"

# 3. Master the audio when it is missing or stale
stale=""
if [[ -n "$REMIX" || ! -f "$MIX" || "$GRID" -nt "$MIX" ]]; then stale=1; fi
for f in "$PROJECT"/audio/scene_*.wav "$PROJECT"/audio/music.wav "$PROJECT"/audio/sfx.wav "$PROJECT"/preset.json "$PROJECT"/mix.json; do
  [[ -f "$f" && "$f" -nt "$MIX" ]] && stale=1
done
if [[ -n "$stale" ]]; then
  "$PY" "$HERE/mix.py" "$PROJECT" || echo "warning: mix.py reported a problem (see above)" >&2
fi

# 4. Subtitles + audio in one pass
FINAL="$OUT/final.mp4"
SRT="$OUT/subtitles.srt"; ASS="$OUT/subtitles.ass"
INPUTS=(-i "$CONCAT"); MAPS=(-map 0:v); VCODEC=(-c:v copy); ACODEC=(-an); SCODEC=(); n=1
if [[ -f "$MIX" ]]; then
  INPUTS+=(-i "$MIX"); MAPS+=(-map "$n:a"); ACODEC=(-c:a aac -b:a 256k -ar 48000); n=$((n+1))
else
  echo "warning: no audio/mix.wav; the video will be silent" >&2
fi
if [[ -n "$BURN" && -f "$ASS" ]]; then
  VCODEC=(-vf "subtitles=${ASS}" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p)
elif [[ -f "$SRT" ]]; then
  INPUTS+=(-i "$SRT"); MAPS+=(-map "$n:s"); SCODEC=(-c:s mov_text -metadata:s:s:0 language=eng)
fi
ffmpeg -y "${INPUTS[@]}" "${MAPS[@]}" "${VCODEC[@]}" "${ACODEC[@]}" "${SCODEC[@]}" \
  -t "$DUR" -movflags +faststart "$FINAL" >/dev/null 2>&1 \
  || { echo "mux failed (re-run without the subtitles to isolate it)" >&2; exit 1; }
[[ -s "$FINAL" ]] || { echo "mux failed" >&2; exit 1; }

echo "-> $FINAL"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$FINAL" 2>/dev/null \
  | awk '{printf "duration: %.1fs\n",$1}'
