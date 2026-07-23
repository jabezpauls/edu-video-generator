#!/usr/bin/env bash
# Copy the shared helpers (springs, formats) into a Manim or Remotion project.
# Usage: scaffold_engine.sh <project-dir> <manim|remotion> [--force]
#   manim:    <project>/scenes/{springs,formats}.py
#   remotion: <project>/scenes/src/{springs.ts,formats.ts,SceneFormats.tsx}
# Existing files are left alone unless --force is given, so scene code can edit its copy.
set -euo pipefail

PROJECT="${1:?usage: scaffold_engine.sh <project-dir> <manim|remotion> [--force]}"
ENGINE="${2:?usage: scaffold_engine.sh <project-dir> <manim|remotion> [--force]}"
FORCE="${3:-}"
TEMPLATES="$(cd "$(dirname "${BASH_SOURCE[0]}")/../templates" && pwd)"

copy() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" && "$FORCE" != "--force" ]]; then
    echo "keep  $dst"
  else
    cp "$src" "$dst"
    echo "write $dst"
  fi
}

case "$ENGINE" in
  manim)
    for f in springs.py formats.py; do copy "$TEMPLATES/manim/$f" "$PROJECT/scenes/$f"; done
    ;;
  remotion)
    for f in springs.ts formats.ts SceneFormats.tsx; do copy "$TEMPLATES/remotion/$f" "$PROJECT/scenes/src/$f"; done
    ;;
  *)
    echo "unknown engine: $ENGINE (use manim or remotion)" >&2
    exit 2
    ;;
esac
