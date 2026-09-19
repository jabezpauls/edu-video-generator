#!/usr/bin/env bash
# Add the motion engine to a project: film/ (engine + starter lesson), timeline.json, package.json.
# Files only, no network: bootstrap.sh installs Playwright afterwards.
# Usage: scaffold_motion.sh <project-dir> [--update]
#   --update  refresh the engine files (core, type, lib, edu, vendor, index.html) and leave your film, timeline and data alone
# Applies the storyboard's preset when it names one (apply_preset.py).
# Safe to re-run: existing film.js, timeline.json and package.json are never overwritten.
set -euo pipefail

PROJECT="${1:?usage: scaffold_motion.sh <project-dir> [--update]}"
UPDATE="${2:-}"
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$SKILL/engines/motion"

[[ -d "$ENGINE" ]] || { echo "motion engine not found at $ENGINE" >&2; exit 1; }

mkdir -p "$PROJECT"/film/lib "$PROJECT"/film/edu "$PROJECT"/renders "$PROJECT"/review "$PROJECT"/assets/fonts

# engine files: copied (not linked) so a project keeps rendering the same after the skill is updated
for f in index.html core.js type.js lib/motion.js lib/motion.test.js lib/time.js; do
  if [[ ! -f "$PROJECT/film/$f" || "$UPDATE" == "--update" ]]; then
    cp "$ENGINE/$f" "$PROJECT/film/$f"
  fi
done
# lesson components and the vendored KaTeX: whole folders, new files added on every run, existing ones kept unless --update
for d in edu vendor; do
  if [[ "$UPDATE" == "--update" ]]; then cp -R "$ENGINE/$d/." "$PROJECT/film/$d/" 2>/dev/null || { mkdir -p "$PROJECT/film/$d"; cp -R "$ENGINE/$d/." "$PROJECT/film/$d/"; }
  else mkdir -p "$PROJECT/film/$d"; cp -Rn "$ENGINE/$d/." "$PROJECT/film/$d/"; fi
done
# the film itself starts as the starter lesson and is yours from then on
[[ -f "$PROJECT/film/film.js" ]] || cp "$ENGINE/starter/lesson.js" "$PROJECT/film/film.js"
[[ -f "$PROJECT/timeline.json" ]] || cp "$SKILL/templates/timeline.json" "$PROJECT/timeline.json"

if [[ ! -f "$PROJECT/package.json" ]]; then
  cat > "$PROJECT/package.json" <<'PKG'
{
  "name": "edu-video-motion",
  "private": true,
  "description": "Motion-engine lesson: seek(t) film rendered with Playwright",
  "devDependencies": { "playwright": "^1.50.0" }
}
PKG
fi

# the storyboard's preset (if it names one) becomes preset.json + assets/fonts/, which sync.mjs hands to the film
PRESET="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('preset') or '')" "$PROJECT/storyboard.json" 2>/dev/null || true)"
if [[ -n "$PRESET" ]]; then
  python3 "$SKILL/scripts/apply_preset.py" "$PRESET" "$PROJECT" >&2 || echo "preset '$PRESET' could not be applied" >&2
fi

# data.js is generated from the timeline (and the storyboard / narration grid when they exist)
if command -v node >/dev/null 2>&1; then
  node "$SKILL/scripts/sync.mjs" --project "$PROJECT" --quiet
else
  echo "node not found: run sync.mjs once node is installed" >&2
fi
echo "$PROJECT/film"
