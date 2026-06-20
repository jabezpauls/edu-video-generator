#!/usr/bin/env bash
# Create the per-run project scaffold and seed manifest.json + storyboard.json stub.
# Usage: new_project.sh <base-dir> <slug>
set -euo pipefail

BASE="${1:?usage: new_project.sh <base-dir> <slug>}"
SLUG="${2:?usage: new_project.sh <base-dir> <slug>}"
PROJECT="$BASE/$SLUG"

mkdir -p "$PROJECT"/{.videogen/{frames,logs,critic},scenes,assets,audio,output}

if [[ ! -f "$PROJECT/manifest.json" ]]; then
  cat > "$PROJECT/manifest.json" <<EOF
{
  "slug": "$SLUG",
  "phase": "intake",
  "engine": null,
  "engine_reason": null,
  "tts_provider": null,
  "render_retries": {},
  "warnings": [],
  "created": "pending"
}
EOF
fi

if [[ ! -f "$PROJECT/storyboard.json" ]]; then
  cat > "$PROJECT/storyboard.json" <<'EOF'
{
  "title": "",
  "audience": "general",
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
