#!/usr/bin/env bash
# Extract critic frames from a rendered scene.
#  Manim:    extract_frames.sh manim    <project> <id>      <t1,t2,...>   (seconds)
#  Remotion: extract_frames.sh remotion <project> <SceneId> <f1,f2,...>   (frame numbers)
# Frames -> <project>/.videogen/frames/scene_<id>_<n>.png  (max 6 enforced by caller)
set -uo pipefail

ENGINE="${1:?engine}"; PROJECT="${2:?project}"; ID="${3:?id}"; POINTS="${4:?points}"
FR="$PROJECT/.videogen/frames"; mkdir -p "$FR"
IFS=',' read -ra PTS <<< "$POINTS"

if [[ "$ENGINE" == "manim" ]]; then
  VID="$PROJECT/output/scene_${ID}.mp4"
  [[ -f "$VID" ]] || { echo "no video: $VID" >&2; exit 1; }
  for t in "${PTS[@]}"; do
    out="$FR/scene_${ID}_${t}.png"
    ffmpeg -y -ss "$t" -i "$VID" -frames:v 1 "$out" >/dev/null 2>&1 \
      && echo "$out" || echo "FAILED t=$t" >&2
  done
elif [[ "$ENGINE" == "remotion" ]]; then
  for f in "${PTS[@]}"; do
    out="$FR/scene_${ID}_f${f}.png"
    ( cd "$PROJECT/scenes" && npx --yes remotion still src/index.ts "Scene${ID}" \
        "../.videogen/frames/scene_${ID}_f${f}.png" --frame="$f" ) >/dev/null 2>&1 \
      && echo "$out" || echo "FAILED frame=$f" >&2
  done
else
  echo "unknown engine: $ENGINE" >&2; exit 2
fi
