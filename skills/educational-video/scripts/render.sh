#!/usr/bin/env bash
# Unified render entrypoint for both engines.
# Usage: render.sh <engine> <project-dir> <scene-id|all> <quality: low|med|high> [format]
#   format: 16x9 | 1x1 | 4x5 | 9x16 | all (every format in the storyboard). Omitted = 16x9 as
#   before. With a format, output is output/scene_<id>.<format>.mp4; without, scene_<id>.mp4.
# Manim scenes:    scenes/scene_<id>.py  with class Scene<Id>
# Remotion scenes: composition id Scene<Id> (16x9) / Scene<Id>-<format> registered in src/Root.tsx
# Output: <project>/output/scene_<id>.mp4  (logs to .videogen/logs/)
set -uo pipefail

ENGINE="${1:?engine}"; PROJECT="${2:?project}"; SCENE="${3:?scene|all}"; Q="${4:-med}"
FORMAT="${5:-}"
case "$FORMAT" in ""|16x9|1x1|4x5|9x16|all) ;; *) echo "unknown format: $FORMAT" >&2; exit 2;; esac
LOGDIR="$PROJECT/.videogen/logs"; OUT="$PROJECT/output"
mkdir -p "$LOGDIR" "$OUT"

render_manim() {
  local id="$1" fmt="${2:-}"
  local cls; cls="Scene$(printf '%s' "$id" | sed 's/^0*//')"   # scene_01 -> Scene1
  # also accept zero-padded class name Scene01
  local file="$PROJECT/scenes/scene_${id}.py"
  local py="$PROJECT/.venv/bin/python"
  local tag="" media="$PROJECT/.videogen/media" out="$OUT/scene_${id}.mp4"
  local -a qargs
  case "$Q" in low) qargs=(-ql);; high) qargs=(-qh);; *) qargs=(-qm);; esac
  if [[ -n "$fmt" ]]; then
    tag=".${fmt}"; media="$media/$fmt"; out="$OUT/scene_${id}.${fmt}.mp4"
  fi
  local log="$LOGDIR/scene_${id}${tag}.render.log"
  [[ -x "$py" ]] || { echo "venv python missing: $py" | tee "$log"; return 3; }
  if [[ -n "$fmt" ]]; then
    # one config file per format sets frame size (units + pixels) before the scene is imported
    local cfg="$PROJECT/.videogen/manim_${fmt}_${Q}.cfg"
    "$py" "$PROJECT/scenes/formats.py" --config "$fmt" "$Q" > "$cfg" 2>>"$log" \
      || { echo "formats.py missing in scenes/ (run scaffold_engine.sh)" | tee -a "$log"; return 3; }
    qargs=(--config_file "$cfg")
  fi
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
  echo ">> manim ${qargs[*]} $file $cls ${fmt:+($fmt)}" | tee "$log"
  ( cd "$PROJECT" && EDU_FORMAT="${fmt:-16x9}" "$py" -m manim "${qargs[@]}" "scenes/scene_${id}.py" "$cls" \
      --media_dir "$media" ) >>"$log" 2>&1
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    local src; src="$(find "$media/videos" -name "${cls}.mp4" 2>/dev/null | head -n1)"
    [[ -n "$src" ]] && cp "$src" "$out" && echo "-> $out" | tee -a "$log"
  fi
  return $rc
}

render_remotion() {
  local id="$1" fmt="${2:-}"
  local comp="Scene${id}" tag="" out="scene_${id}.mp4"
  if [[ -n "$fmt" ]]; then
    tag=".${fmt}"; out="scene_${id}.${fmt}.mp4"
    [[ "$fmt" != "16x9" ]] && comp="Scene${id}-${fmt}"
  fi
  local log="$LOGDIR/scene_${id}${tag}.render.log"
  echo ">> remotion render $comp" | tee "$log"
  ( cd "$PROJECT/scenes" && npx --yes remotion render src/index.ts "$comp" \
      "../output/$out" ) >>"$log" 2>&1
  return $?
}

scene_ids() {
  if [[ "$SCENE" == "all" ]]; then
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('\n'.join(s['id'] for s in d['scenes']))" \
      "$PROJECT/storyboard.json"
  else
    echo "$SCENE"
  fi
}

# formats to render: "" (legacy, 16x9), one format, or every format in the storyboard
format_list() {
  if [[ "$FORMAT" == "all" ]]; then
    python3 -c "import json,sys; print('\n'.join(json.load(open(sys.argv[1])).get('formats') or ['16x9']))" \
      "$PROJECT/storyboard.json"
  else
    echo "$FORMAT"
  fi
}

RC=0
while read -r id; do
  [[ -z "$id" ]] && continue
  while IFS= read -r fmt; do
    case "$ENGINE" in
      manim)    render_manim "$id" "$fmt"    || RC=$?;;
      remotion) render_remotion "$id" "$fmt" || RC=$?;;
      *) echo "unknown engine: $ENGINE" >&2; exit 2;;
    esac
  done < <(format_list)
done < <(scene_ids)

exit $RC
