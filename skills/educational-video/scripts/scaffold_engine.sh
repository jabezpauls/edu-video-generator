#!/usr/bin/env bash
# Copy the shared helpers (springs, formats) into a Manim or Remotion project.
# Usage: scaffold_engine.sh <project-dir> <manim|remotion> [--force]
#   manim:    <project>/scenes/{springs,formats,gridsync}.py
#   remotion: <project>/scenes/src/{springs.ts,formats.ts,SceneFormats.tsx,gridsync.ts}
# Existing files are left alone unless --force is given, so scene code can edit its copy.
# Also writes the theme (scenes/theme.py, scenes/src/theme.ts) from the storyboard's preset, or
# from the blank preset's defaults when none is named, so scene code can always import it.
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
    copy "$TEMPLATES/gridsync.py" "$PROJECT/scenes/gridsync.py"
    ;;
  remotion)
    for f in springs.ts formats.ts SceneFormats.tsx; do copy "$TEMPLATES/remotion/$f" "$PROJECT/scenes/src/$f"; done
    copy "$TEMPLATES/gridsync.ts" "$PROJECT/scenes/src/gridsync.ts"
    ;;
  *)
    echo "unknown engine: $ENGINE (use manim or remotion)" >&2
    exit 2
    ;;
esac

# Theme: apply the storyboard's preset (or refresh the theme only if it is missing).
PRESET=""
if [[ -f "$PROJECT/storyboard.json" ]]; then
  PRESET="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('preset') or '')" \
    "$PROJECT/storyboard.json" 2>/dev/null || true)"
fi
THEME="$PROJECT/scenes/theme.py"; [[ "$ENGINE" == "remotion" ]] && THEME="$PROJECT/scenes/src/theme.ts"
if [[ -n "$PRESET" || ! -e "$THEME" ]]; then
  python3 "$(dirname "${BASH_SOURCE[0]}")/apply_preset.py" "${PRESET:-blank}" "$PROJECT"
fi
