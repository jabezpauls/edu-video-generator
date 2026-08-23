#!/usr/bin/env bash
# Create the per-run project scaffold and seed manifest.json + storyboard.json stub.
# Usage: new_project.sh <base-dir> <slug> [manim|remotion|motion]
#   With an engine, the choice is recorded in manifest.json and storyboard.json. For `motion` the engine
#   files, a starter lesson and timeline.json are laid down too (scaffold_motion.sh; Playwright comes from bootstrap.sh).
set -euo pipefail

BASE="${1:?usage: new_project.sh <base-dir> <slug> [manim|remotion|motion]}"
SLUG="${2:?usage: new_project.sh <base-dir> <slug> [manim|remotion|motion]}"
ENGINE="${3:-}"
PROJECT="$BASE/$SLUG"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The slug goes straight into JSON and a directory name, so keep it boring.
if [[ ! "$SLUG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "invalid slug '$SLUG' (use letters, digits, '.', '_' or '-')" >&2
  exit 2
fi

case "$ENGINE" in
  ""|manim|remotion|motion) ;;
  *) echo "unknown engine '$ENGINE' (use manim, remotion or motion)" >&2; exit 2;;
esac
if [[ -n "$ENGINE" ]]; then ENGINE_JSON="\"$ENGINE\""; else ENGINE_JSON="null"; fi

mkdir -p "$PROJECT"/{.videogen/{frames,logs,critic},scenes,assets,audio,output}

if [[ ! -f "$PROJECT/manifest.json" ]]; then
  cat > "$PROJECT/manifest.json" <<EOF
{
  "slug": "$SLUG",
  "phase": "intake",
  "engine": $ENGINE_JSON,
  "engine_reason": null,
  "mode": "lesson",
  "formats": ["16x9"],
  "preset": null,
  "tts_provider": null,
  "render_retries": {},
  "critic_rounds": 0,
  "scores": {},
  "warnings": [],
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
fi

if [[ ! -f "$PROJECT/storyboard.json" ]]; then
  cat > "$PROJECT/storyboard.json" <<EOF
{
  "title": "",
  "audience": "general",
  "mode": "lesson",
  "formats": ["16x9"],
  "preset": null,
  "aspect_ratio": "16:9",
  "resolution": "1920x1080",
  "fps": 30,
  "engine": $ENGINE_JSON,
  "engine_reason": "",
  "language": "en",
  "narration": true,
  "target_duration_s": 120,
  "scenes": []
}
EOF
fi

if [[ "$ENGINE" == "motion" ]]; then
  "$HERE/scaffold_motion.sh" "$PROJECT" >&2
fi

echo "$PROJECT"
