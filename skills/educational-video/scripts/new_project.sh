#!/usr/bin/env bash
# Create the per-run project scaffold and seed manifest.json + storyboard.json stub.
# Usage: new_project.sh <base-dir> <slug>
set -euo pipefail

BASE="${1:?usage: new_project.sh <base-dir> <slug>}"
SLUG="${2:?usage: new_project.sh <base-dir> <slug>}"
PROJECT="$BASE/$SLUG"

# The slug goes straight into JSON and a directory name, so keep it boring.
if [[ ! "$SLUG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "invalid slug '$SLUG' (use letters, digits, '.', '_' or '-')" >&2
  exit 2
fi

mkdir -p "$PROJECT"/{.videogen/{frames,logs,critic},scenes,assets,audio,output}

if [[ ! -f "$PROJECT/manifest.json" ]]; then
  cat > "$PROJECT/manifest.json" <<EOF
{
  "slug": "$SLUG",
  "phase": "intake",
  "engine": null,
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
  cat > "$PROJECT/storyboard.json" <<'EOF'
{
  "title": "",
  "audience": "general",
  "mode": "lesson",
  "formats": ["16x9"],
  "preset": null,
  "aspect_ratio": "16:9",
  "resolution": "1920x1080",
  "fps": 30,
  "engine": null,
  "engine_reason": "",
  "language": "en",
  "narration": true,
  "target_duration_s": 120,
  "scenes": []
}
EOF
fi

echo "$PROJECT"
