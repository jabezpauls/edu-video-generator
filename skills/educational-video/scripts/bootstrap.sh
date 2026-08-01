#!/usr/bin/env bash
# Idempotent environment bootstrap for the educational-video skill.
# Usage: bootstrap.sh <project-dir> <engine: manim|remotion|motion|auto>
# Detects what's present and installs only what's missing. Never uses system
# Python for Manim (Manim breaks on Python 3.14 — use a pinned uv 3.12 venv).
# `auto` sets up Manim and Remotion and only probes for the motion engine (node + ffmpeg); once a lesson is
# routed to motion, run `bootstrap.sh <project> motion` to scaffold it and install Playwright + Chromium.
set -uo pipefail

PROJECT="${1:?usage: bootstrap.sh <project-dir> <engine>}"
ENGINE="${2:-auto}"
PYVER="3.12"

log()  { printf '\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[bootstrap]\033[0m %s\n' "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

mkdir -p "$PROJECT/.videogen"
ENVJSON="$PROJECT/.videogen/env.json"
MANIM_OK=false; REMOTION_OK=false; MOTION_OK=false

# --- System probe (do not reinstall what's present) ---
for t in ffmpeg uv node npm; do
  if have "$t"; then log "found $t: $($t --version 2>&1 | head -n1)"; else warn "MISSING $t"; fi
done
if have pdflatex; then log "found pdflatex (LaTeX ok)"; else warn "pdflatex missing — Manim LaTeX disabled"; fi

# --- Python venv via uv, pinned to 3.12 ---
if [[ "$ENGINE" == "manim" || "$ENGINE" == "auto" ]]; then
  if have uv; then
    if [[ ! -x "$PROJECT/.venv/bin/python" ]]; then
      log "creating venv ($PYVER) via uv"
      uv python install "$PYVER" >/dev/null 2>&1 || warn "uv python install $PYVER had issues"
      uv venv --python "$PYVER" "$PROJECT/.venv" || warn "uv venv failed"
    else
      log "venv already present"
    fi
    if [[ -x "$PROJECT/.venv/bin/python" ]]; then
      if ! "$PROJECT/.venv/bin/python" -c "import manim" 2>/dev/null; then
        log "installing manim into venv"
        if VIRTUAL_ENV="$PROJECT/.venv" uv pip install --python "$PROJECT/.venv/bin/python" "manim>=0.19"; then
          log "manim installed"
        else
          warn "manim install failed"
        fi
      else
        log "manim already importable"
      fi
      # smoke test
      if "$PROJECT/.venv/bin/python" -c "import manim" 2>/dev/null; then MANIM_OK=true; fi
    fi
  else
    warn "uv not found — cannot set up Manim venv"
  fi
fi

# --- Remotion scaffold ---
if [[ "$ENGINE" == "remotion" || "$ENGINE" == "auto" ]]; then
  if have npm; then
    if [[ ! -f "$PROJECT/scenes/package.json" ]]; then
      log "scaffolding Remotion project under scenes/"
      mkdir -p "$PROJECT/scenes"
      # minimal manual scaffold (avoids interactive create-video prompts)
      cat > "$PROJECT/scenes/package.json" <<'PKG'
{
  "name": "edu-video-scenes",
  "version": "1.0.0",
  "private": true,
  "scripts": { "render": "remotion render", "still": "remotion still" },
  "dependencies": {
    "@remotion/cli": "^4.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "remotion": "^4.0.0"
  },
  "devDependencies": { "@types/react": "^18.0.0", "typescript": "^5.0.0" }
}
PKG
      cat > "$PROJECT/scenes/remotion.config.ts" <<'CFG'
import { Config } from "@remotion/cli/config";
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
CFG
      cat > "$PROJECT/scenes/tsconfig.json" <<'TS'
{ "compilerOptions": { "target": "ES2018", "module": "ESNext", "jsx": "react-jsx",
  "moduleResolution": "node", "esModuleInterop": true, "strict": true, "skipLibCheck": true } }
TS
      mkdir -p "$PROJECT/scenes/src"
      cat > "$PROJECT/scenes/src/index.ts" <<'IDX'
import { registerRoot } from "remotion";
import { Root } from "./Root";
registerRoot(Root);
IDX
      cat > "$PROJECT/scenes/src/Root.tsx" <<'ROOT'
// Scenes are appended here by the Coder. Each scene = one <Composition>.
import React from "react";
export const Root: React.FC = () => (<></>);
ROOT
      if ( cd "$PROJECT/scenes" && npm install >/dev/null 2>&1 ); then
        log "Remotion deps installed"
      else
        warn "npm install failed in scenes/"
      fi
    else
      log "Remotion project already scaffolded"
    fi
    # pre-warm headless chrome
    if ( cd "$PROJECT/scenes" && npx --yes remotion browser ensure >/dev/null 2>&1 ); then
      log "Chrome headless shell ready"
    else
      warn "could not pre-warm Chrome (will retry at render)"
    fi
    [[ -f "$PROJECT/scenes/package.json" ]] && REMOTION_OK=true
  else
    warn "npm not found — cannot set up Remotion"
  fi
fi

# --- Motion engine: scaffold + Playwright (renders the seek(t) film in headless Chromium) ---
if [[ "$ENGINE" == "motion" ]]; then
  if have node && have npm && have ffmpeg; then
    "$(dirname "$0")/scaffold_motion.sh" "$PROJECT" >/dev/null || warn "motion scaffold failed"
    if ( cd "$PROJECT" && node -e "require.resolve('playwright')" ) 2>/dev/null; then
      log "playwright already installed"
    elif ( cd "$PROJECT" && npm install --no-audit --no-fund >/dev/null 2>&1 ); then
      log "playwright installed"
    else
      warn "npm install failed in $PROJECT"
    fi
    if ( cd "$PROJECT" && npx --yes playwright install chromium >/dev/null 2>&1 ); then
      log "Chromium ready for the motion engine"
    else
      warn "could not install Chromium (playwright install chromium)"
    fi
    # smoke test: the browser must actually start
    if ( cd "$PROJECT" && node -e "
      require('playwright').chromium.launch().then(b => b.close().then(() => process.exit(0)), e => { console.error(e.message); process.exit(1); });
    " ) >/dev/null 2>&1; then
      MOTION_OK=true
    else
      warn "headless Chromium did not start; see references/troubleshooting.md"
    fi
  else
    warn "motion engine needs node, npm and ffmpeg"
  fi
elif [[ "$ENGINE" == "auto" ]]; then
  if have node && have ffmpeg; then MOTION_OK=true; fi
fi

# --- TTS detection ---
TTS_JSON="{}"
if [[ -f "$(dirname "$0")/detect_tts.py" ]]; then
  TTS_JSON="$(python3 "$(dirname "$0")/detect_tts.py" "$PROJECT" 2>/dev/null || echo '{}')"
fi

# --- Write capability descriptor ---
cat > "$ENVJSON" <<EOF
{
  "manim_ok": $MANIM_OK,
  "remotion_ok": $REMOTION_OK,
  "motion_ok": $MOTION_OK,
  "python_venv": "$PROJECT/.venv/bin/python",
  "tts": $TTS_JSON
}
EOF
log "wrote $ENVJSON"
log "done (manim_ok=$MANIM_OK remotion_ok=$REMOTION_OK motion_ok=$MOTION_OK)"
