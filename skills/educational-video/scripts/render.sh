#!/usr/bin/env bash
# Unified render entrypoint for both engines.
# Usage: render.sh <engine> <project-dir> <scene-id|all> <quality: low|med|high>
# Manim scenes:    scenes/scene_<id>.py  with class Scene<Id>
# Remotion scenes: composition id Scene<Id> registered in src/Root.tsx
# Output: <project>/output/scene_<id>.mp4  (logs to .videogen/logs/)
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

scene_ids() {
  if [[ "$SCENE" == "all" ]]; then
    python3 -c "import json,sys; d=json.load(open('$PROJECT/storyboard.json')); print('\n'.join(s['id'] for s in d['scenes']))"
  else
    echo "$SCENE"
  fi
}

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
