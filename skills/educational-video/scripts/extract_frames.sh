#!/usr/bin/env bash
# Extract critic frames from a rendered scene.
#  Manim:    extract_frames.sh manim    <project> <id>      <t1,t2,...>   (seconds)
#  Remotion: extract_frames.sh remotion <project> <SceneId> <f1,f2,...>   (frame numbers)
#  Any engine, from a rendered file (final lesson critic):
#            extract_frames.sh video <project> <name> <t1,t2,...> <file.mp4>   (seconds)
#   For manim/remotion, an optional 5th arg <format> (1x1 | 4x5 | 9x16 | 16x9) picks the
#   per-format render and names the frames scene_<id>.<format>_<n>.png.
# Frames -> <project>/.videogen/frames/scene_<id>_<n>.png  (max 6 enforced by caller)
set -uo pipefail

ENGINE="${1:?engine}"; PROJECT="${2:?project}"; ID="${3:?id}"; POINTS="${4:?points}"
FILE=""; FMT=""
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
else
  echo "unknown engine: $ENGINE" >&2; exit 2
fi
