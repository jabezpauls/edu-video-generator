#!/usr/bin/env bash
# Extract critic frames from a rendered scene.
#  Manim:    extract_frames.sh manim    <project> <id>      <t1,t2,...>   (seconds)
#  Remotion: extract_frames.sh remotion <project> <SceneId> <f1,f2,...>   (frame numbers)
#  Any engine, from a rendered file (final lesson critic):
#            extract_frames.sh video <project> <name> <t1,t2,...> <file.mp4>   (seconds)
#   For manim/remotion, an optional 5th arg <format> (1x1 | 4x5 | 9x16 | 16x9) picks the
#   per-format render and names the frames scene_<id>.<format>_<n>.png.
#  Motion:   extract_frames.sh motion   <project> <id|all>  <t1,t2,...>   [format]  (seconds)
#            <id>: seconds into output/scene_<id>.mp4 (from `render.sh motion <project> <id>`);
#            all: seconds on the whole film, from the newest render of the first format (FMT=9x16 picks another):
#            renders/<fmt>.mp4, else preview_<fmt>.mp4, else draft_<fmt>.mp4
# Frames -> <project>/.videogen/frames/scene_<id>_<n>.png  (max 6 enforced by caller)
set -uo pipefail

ENGINE="${1:?engine}"; PROJECT="${2:?project}"; ID="${3:?id}"; POINTS="${4:?points}"
ENV_FMT="${FMT:-}"; FILE=""; FMT=""
if [[ "$ENGINE" == "video" ]]; then FILE="${5:-}"; else FMT="${5:-}"; fi
TAG=""; COMP="Scene${ID}"
if [[ -n "$FMT" ]]; then
  TAG=".${FMT}"
  [[ "$FMT" != "16x9" ]] && COMP="Scene${ID}-${FMT}"
fi
FR="$PROJECT/.videogen/frames"; mkdir -p "$FR"
IFS=',' read -ra PTS <<< "$POINTS"

if [[ "$ENGINE" == "manim" ]]; then
  VID="$PROJECT/output/scene_${ID}${TAG}.mp4"
  [[ -f "$VID" ]] || { echo "no video: $VID" >&2; exit 1; }
  for t in "${PTS[@]}"; do
    out="$FR/scene_${ID}${TAG}_${t}.png"
    ffmpeg -y -ss "$t" -i "$VID" -frames:v 1 "$out" >/dev/null 2>&1 \
      && echo "$out" || echo "FAILED t=$t" >&2
  done
elif [[ "$ENGINE" == "remotion" ]]; then
  for f in "${PTS[@]}"; do
    out="$FR/scene_${ID}${TAG}_f${f}.png"
    ( cd "$PROJECT/scenes" && npx --yes remotion still src/index.ts "$COMP" \
        "../.videogen/frames/scene_${ID}${TAG}_f${f}.png" --frame="$f" ) >/dev/null 2>&1 \
      && echo "$out" || echo "FAILED frame=$f" >&2
  done
elif [[ "$ENGINE" == "video" ]]; then
  [[ -f "$FILE" ]] || { echo "no video: ${FILE:-<missing file argument>}" >&2; exit 1; }
  for t in "${PTS[@]}"; do
    out="$FR/${ID}_${t}.png"
    ffmpeg -y -ss "$t" -i "$FILE" -frames:v 1 "$out" >/dev/null 2>&1 \
      && echo "$out" || echo "FAILED t=$t" >&2
  done
elif [[ "$ENGINE" == "motion" ]]; then
  FMT="${FMT:-$ENV_FMT}"   # 5th arg, or FMT= in the environment
  if [[ "$ID" == "all" ]]; then
    FMT="${FMT:-$(python3 -c "import json,sys; import re; print(json.loads(re.search(r'^window.TL = (.*);\$', open(sys.argv[1]).read(), re.M).group(1)).get('formats', ['16x9'])[0])" "$PROJECT/film/data.js" 2>/dev/null || echo 16x9)}"
    VID=""
    for cand in "$PROJECT/renders/$FMT.mp4" "$PROJECT/renders/preview_$FMT.mp4" "$PROJECT/renders/draft_$FMT.mp4"; do
      [[ -f "$cand" ]] && { VID="$cand"; break; }
    done
    [[ -n "$VID" ]] || { echo "no render of $FMT in $PROJECT/renders (run render.sh motion <project> all low)" >&2; exit 1; }
  else
    VID="$PROJECT/output/scene_${ID}.mp4"
    [[ -f "$VID" ]] || { echo "no video: $VID" >&2; exit 1; }
  fi
  for t in "${PTS[@]}"; do
    out="$FR/scene_${ID}_${t}.png"
    ffmpeg -y -ss "$t" -i "$VID" -frames:v 1 "$out" >/dev/null 2>&1 \
      && echo "$out" || echo "FAILED t=$t" >&2
  done
else
  echo "unknown engine: $ENGINE" >&2; exit 2
fi
