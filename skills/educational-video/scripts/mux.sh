#!/usr/bin/env bash
# Assemble the final video from per-scene renders (Manim / Remotion) and the mastered mix.
#
# Usage: mux.sh <project-dir> [--format 16x9|1x1|4x5|9x16|all] [--burn] [--remix]
#   --format F  which format to assemble; `all` does every format in storyboard.json. Default: the primary
#               (first) format. Scene videos are scene_<id>.<F>.mp4 (render.sh <engine> <p> all <q> F); a 16x9
#               render without the format suffix (scene_<id>.mp4) is accepted for 16x9.
#   --burn      hardcode subtitles.ass into the picture (default: soft-mux subtitles.srt)
#   --remix     rebuild audio/mix.wav even if it is up to date
#
# Output: the primary format is output/final.mp4, every other format output/final_<F>.mp4.
# 9x16 always gets burned-in captions (output/subtitles_9x16.ass, kept clear of the platform UI zones) because
# players show no subtitle track there; the others get a soft mov_text track.
#
# Needs grid.json (scripts/grid.py). Each scene video is conformed to its grid duration (the
# last frame is held if the render is short, extra frames are trimmed), the scenes are
# concatenated, and audio/mix.wav (narration + bed + sfx at -14 LUFS, see mix.py) is muxed in.
# The mix is rebuilt first when it is missing or older than its inputs.
set -uo pipefail

PROJECT=""; BURN=""; REMIX=""; FORMAT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --burn) BURN=1;;
    --remix) REMIX=1;;
    --format) shift; FORMAT="${1:-}";;
    --format=*) FORMAT="${1#--format=}";;
    -*) echo "unknown option: $1" >&2; exit 2;;
    *) PROJECT="$1";;
  esac
  shift
done
[[ -n "$PROJECT" ]] || { echo "usage: mux.sh <project-dir> [--format 16x9|1x1|4x5|9x16|all] [--burn] [--remix]" >&2; exit 2; }
case "$FORMAT" in ""|16x9|1x1|4x5|9x16|all) ;; *) echo "unknown format: $FORMAT" >&2; exit 2;; esac

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

# formats of the storyboard, primary first (a mode's default applies when it lists none)
mapfile -t SB_FORMATS < <("$PY" -c "
import json,sys
try: sb=json.load(open(sys.argv[1]))
except (OSError, ValueError): sb={}
f=sb.get('formats') or (['9x16'] if sb.get('mode')=='short' else ['16x9'])
print('\n'.join(f))" "$PROJECT/storyboard.json")
PRIMARY="${SB_FORMATS[0]}"
case "$FORMAT" in
  "") WANT=("$PRIMARY");;
  all) WANT=("${SB_FORMATS[@]}");;
  *) WANT=("$FORMAT");;
esac

# Master the audio once, when it is missing or stale
stale=""
if [[ -n "$REMIX" || ! -f "$MIX" || "$GRID" -nt "$MIX" ]]; then stale=1; fi
for f in "$PROJECT"/audio/scene_*.wav "$PROJECT"/audio/music.wav "$PROJECT"/audio/sfx.wav "$PROJECT"/preset.json "$PROJECT"/mix.json; do
  [[ -f "$f" && "$f" -nt "$MIX" ]] && stale=1
done
if [[ -n "$stale" ]]; then
  "$PY" "$HERE/mix.py" "$PROJECT" || echo "warning: mix.py reported a problem (see above)" >&2
fi

# Assemble one format
mux_format() {
  local fmt="$1"
  local tmp="$TMP/$fmt" final="$OUT/final_${fmt}.mp4"
  [[ "$fmt" == "$PRIMARY" ]] && final="$OUT/final.mp4"
  mkdir -p "$tmp"
  # 1. Conform each scene video to its grid duration (video only; the mix carries all audio)
  local list="$tmp/concat.txt" row id want v seg have delta filt segpath
  : > "$list"
  for row in "${ROWS[@]}"; do
    id="${row%% *}"; want="${row#* }"
    v="$OUT/scene_${id}.${fmt}.mp4"; seg="$tmp/seg_${id}.mp4"
    [[ -f "$v" || "$fmt" != "16x9" ]] || v="$OUT/scene_${id}.mp4"
    [[ -f "$v" ]] || { echo "missing scene video: $v (render it: render.sh <engine> $PROJECT $id <quality> $fmt)" >&2; return 1; }
    have="$(probe "$v")"
    delta="$(awk -v h="$have" -v w="$want" 'BEGIN{printf "%.3f", w-h}')"
    filt="fps=${FPS}"
    if awk -v d="$delta" 'BEGIN{exit !(d>0.02)}'; then
      filt="${filt},tpad=stop_mode=clone:stop_duration=${delta}"
      awk -v d="$delta" 'BEGIN{exit !(d>0.25)}' \
        && echo "warning: scene $id ($fmt) render is ${delta}s shorter than its narration slot (last frame held); extend the animation" >&2
    elif awk -v d="$delta" 'BEGIN{exit !(d<-0.1)}'; then
      echo "warning: scene $id ($fmt) render is ${delta#-}s longer than its slot (trimmed); shorten the animation" >&2
    fi
    ffmpeg -y -i "$v" -an -vf "$filt" -t "$want" -c:v libx264 -preset medium -crf 18 \
      -pix_fmt yuv420p "$seg" >/dev/null 2>&1 \
      || { echo "could not conform scene $id ($fmt)" >&2; return 1; }
    segpath="$(cd "$tmp" && pwd)/seg_${id}.mp4"
    echo "file '${segpath//\'/\'\\\'\'}'" >> "$list"   # concat-demuxer quoting for paths with quotes
  done

  # 2. Concat the conformed scenes (identical encodes, so stream copy)
  local concat="$tmp/concat.mp4" dur
  ffmpeg -y -f concat -safe 0 -i "$list" -c copy "$concat" >/dev/null 2>&1 \
    || { echo "concat failed ($fmt)" >&2; return 1; }
  dur="$(probe "$concat")"

  # 3. Subtitles + audio in one pass
  local srt="$OUT/subtitles.srt" ass="$OUT/subtitles.ass" n=1
  local -a inputs=(-i "$concat") maps=(-map 0:v) vcodec=(-c:v copy) acodec=(-an) scodec=()
  [[ "$fmt" == "9x16" ]] && { ass="$OUT/subtitles_9x16.ass"; BURN_THIS=1; } || BURN_THIS="$BURN"
  if [[ -f "$MIX" ]]; then
    inputs+=(-i "$MIX"); maps+=(-map "$n:a"); acodec=(-c:a aac -b:a 256k -ar 48000); n=$((n+1))
  else
    echo "warning: no audio/mix.wav; the video will be silent" >&2
  fi
  if [[ -n "$BURN_THIS" && -f "$ass" ]]; then
    local esc="${ass//\\/\\\\}"; esc="${esc//:/\\:}"; esc="${esc//\'/\\\'}"
    vcodec=(-vf "subtitles=filename='${esc}'" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p)
  elif [[ "$fmt" == "9x16" ]]; then
    echo "warning: $ass missing: the 9x16 video has no captions (run align_subtitles.py $PROJECT)" >&2
  elif [[ -f "$srt" ]]; then
    inputs+=(-i "$srt"); maps+=(-map "$n:s"); scodec=(-c:s mov_text -metadata:s:s:0 language=eng)
  fi
  ffmpeg -y "${inputs[@]}" "${maps[@]}" "${vcodec[@]}" "${acodec[@]}" "${scodec[@]}" \
    -t "$dur" -movflags +faststart "$final" >/dev/null 2>&1 \
    || { echo "mux failed for $fmt (re-run without the subtitles to isolate it)" >&2; return 1; }
  [[ -s "$final" ]] || { echo "mux failed for $fmt" >&2; return 1; }

  echo "-> $final"
  probe "$final" | awk '{printf "duration: %.1fs\n",$1}'
}

RC=0
for fmt in "${WANT[@]}"; do mux_format "$fmt" || RC=1; done
exit $RC
