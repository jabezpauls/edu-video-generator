#!/usr/bin/env bash
# Unified render entrypoint for all three engines.
# Usage: render.sh <engine> <project-dir> <scene-id|all> <quality: low|med|high>
# Manim scenes:    scenes/scene_<id>.py  with class Scene<Id>
# Remotion scenes: composition id Scene<Id> registered in src/Root.tsx
# Output: <project>/output/scene_<id>.mp4  (logs to .videogen/logs/)
#
# Motion lessons are ONE film (film/film.js + timeline.json), rendered by render.mjs; this script delegates:
#   render.sh motion <project> all   low|med|high   every format in timeline.json -> renders/, then output/
#   render.sh motion <project> <id>  low|med|high   one scene (film scene "s<id>") of the first format -> output/scene_<id>.mp4
#   quality: low = 30 fps draft, med = 30 fps no blur CRF 18, high = 60 fps with adaptive motion blur (final)
#   extra modes for motion: `verify` (determinism check of every format) and `sheet` (contact sheets)
#   set FMT=9x16 to render one scene in another format. `all` writes output/final.mp4 (high) or
#   output/preview.mp4 (low, med) for the first format and output/<name>_<fmt>.mp4 for the others.
set -uo pipefail

ENGINE="${1:?engine}"; PROJECT="${2:?project}"; SCENE="${3:?scene|all}"; Q="${4:-med}"
LOGDIR="$PROJECT/.videogen/logs"; OUT="$PROJECT/output"
mkdir -p "$LOGDIR" "$OUT"

render_manim() {
  local id="$1"
  local cls; cls="Scene$(printf '%s' "$id" | sed 's/^0*//')"   # scene_01 -> Scene1
  # also accept zero-padded class name Scene01
  local file="$PROJECT/scenes/scene_${id}.py"
  local py="$PROJECT/.venv/bin/python"
  local mq; case "$Q" in low) mq="-ql";; high) mq="-qh";; *) mq="-qm";; esac
  local log="$LOGDIR/scene_${id}.render.log"
  [[ -x "$py" ]] || { echo "venv python missing: $py" | tee "$log"; return 3; }
  # discover the actual class name in the file (first Scene subclass)
  local found
  found="$("$py" - "$file" <<'PY' 2>/dev/null
import ast,sys
src=open(sys.argv[1]).read()
for n in ast.walk(ast.parse(src)):
    if isinstance(n,ast.ClassDef):
        print(n.name); break
PY
)"
  [[ -n "$found" ]] && cls="$found"
  echo ">> manim $mq $file $cls" | tee "$log"
  ( cd "$PROJECT" && "$py" -m manim "$mq" "scenes/scene_${id}.py" "$cls" \
      --media_dir "$PROJECT/.videogen/media" ) >>"$log" 2>&1
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    local src; src="$(find "$PROJECT/.videogen/media/videos" -name "${cls}.mp4" 2>/dev/null | head -n1)"
    [[ -n "$src" ]] && cp "$src" "$OUT/scene_${id}.mp4" && echo "-> $OUT/scene_${id}.mp4" | tee -a "$log"
  fi
  return $rc
}

render_remotion() {
  local id="$1"
  local comp; comp="Scene${id}"
  local log="$LOGDIR/scene_${id}.render.log"
  echo ">> remotion render $comp" | tee "$log"
  ( cd "$PROJECT/scenes" && npx --yes remotion render src/index.ts "$comp" \
      "../output/scene_${id}.mp4" ) >>"$log" 2>&1
  return $?
}

render_motion() {
  local scene="$1"
  local here; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local abs; abs="$(cd "$PROJECT" && pwd)"
  local log="$LOGDIR/motion_${scene}.render.log"
  have_node || return 3
  local -a flags=()
  local tag="" dest="final"
  case "$Q" in
    low) flags=(--draft); tag="draft_"; dest="preview";;
    med) flags=(--blur 0 --fps 30 --crf 18 --tag preview); tag="preview_"; dest="preview";;
    high) flags=();;
    verify|sheet) flags=("--$Q");;
    *) echo "unknown quality for motion: $Q (low|med|high|verify|sheet)" >&2; return 2;;
  esac
  : > "$log"
  echo ">> sync + render.mjs $Q ($scene)" | tee -a "$log"
  node "$here/sync.mjs" --project "$abs" --quiet >>"$log" 2>&1 || { tail -n 5 "$log" >&2; return 1; }
  local -a formats
  mapfile -t formats < <(node -e "const t=JSON.parse(require('fs').readFileSync(process.argv[1]+'/timeline.json','utf8'));console.log((t.formats||['16x9']).join('\\n'))" "$abs")
  local first="${formats[0]}"
  local rc=0
  if [[ "$scene" == "all" ]]; then
    node "$here/render.mjs" --project "$abs" --all "${flags[@]}" >>"$log" 2>&1 || rc=$?
    if [[ $rc -eq 0 && "$Q" != "verify" && "$Q" != "sheet" ]]; then
      local fmt name
      for fmt in "${formats[@]}"; do
        name="${dest}_${fmt}.mp4"; [[ "$fmt" == "$first" ]] && name="${dest}.mp4"
        cp "$abs/renders/${tag}${fmt}.mp4" "$OUT/$name" && echo "-> $OUT/$name" | tee -a "$log"
      done
    fi
  else
    node "$here/render.mjs" --project "$abs" --scene "$scene" --fmt "${FMT:-$first}" \
      --out "$abs/output/scene_${scene}.mp4" "${flags[@]}" >>"$log" 2>&1 || rc=$?
    [[ $rc -eq 0 ]] && echo "-> $OUT/scene_${scene}.mp4" | tee -a "$log"
  fi
  if [[ $rc -ne 0 ]]; then echo "motion render failed (see $log):" >&2; tail -n 8 "$log" >&2; fi
  return $rc
}

have_node() { command -v node >/dev/null 2>&1 || { echo "node not found" >&2; return 1; }; }

scene_ids() {
  if [[ "$SCENE" == "all" ]]; then
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('\n'.join(s['id'] for s in d['scenes']))" \
      "$PROJECT/storyboard.json"
  else
    echo "$SCENE"
  fi
}

if [[ "$ENGINE" == "motion" ]]; then
  render_motion "$SCENE"
  exit $?
fi

RC=0
while read -r id; do
  [[ -z "$id" ]] && continue
  case "$ENGINE" in
    manim)    render_manim "$id"    || RC=$?;;
    remotion) render_remotion "$id" || RC=$?;;
    *) echo "unknown engine: $ENGINE" >&2; exit 2;;
  esac
done < <(scene_ids)

exit $RC
