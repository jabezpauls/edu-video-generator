#!/usr/bin/env bash
# Create the per-run project scaffold and seed manifest.json + storyboard.json stub.
# Usage: new_project.sh <base-dir> <slug> [manim|remotion|motion] [--short]
#   --short  a 30-60 s vertical micro-lesson: mode short, formats ["9x16"], engine motion unless you name one, and
#            storyboard.json starts as templates/short.storyboard.json (hook, idea, example, payoff, recap).
#   With an engine, the choice is recorded in manifest.json and storyboard.json. For `motion` the engine
#   files, a starter lesson and timeline.json are laid down too (scaffold_motion.sh; Playwright comes from bootstrap.sh).
set -euo pipefail

USAGE="usage: new_project.sh <base-dir> <slug> [manim|remotion|motion] [--short]"
SHORT=""; ARGS=()
for a in "$@"; do
  case "$a" in
    --short) SHORT=1;;
    -*) echo "unknown option '$a'" >&2; echo "$USAGE" >&2; exit 2;;
    *) ARGS+=("$a");;
  esac
done
BASE="${ARGS[0]:?$USAGE}"
SLUG="${ARGS[1]:?$USAGE}"
ENGINE="${ARGS[2]:-}"
REASON="null"
[[ -z "$ENGINE" && -n "$SHORT" ]] && { ENGINE="motion"; REASON='"short mode default"'; }
PROJECT="$BASE/$SLUG"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="lesson"; FORMATS_JSON='["16x9"]'
if [[ -n "$SHORT" ]]; then MODE="short"; FORMATS_JSON='["9x16"]'; fi

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
  "engine_reason": $REASON,
  "mode": "$MODE",
  "formats": $FORMATS_JSON,
  "preset": null,
  "tts_provider": null,
  "render_retries": {},
  "critic_mode": null,
  "critic_rounds": 0,
  "scores": {},
  "warnings": [],
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
fi

if [[ ! -f "$PROJECT/storyboard.json" && -n "$SHORT" ]]; then
  cp "$HERE/../templates/short.storyboard.json" "$PROJECT/storyboard.json"
elif [[ ! -f "$PROJECT/storyboard.json" ]]; then
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
