#!/usr/bin/env bash
# Install the educational-video skill (v2) into Claude Code's skills directory.
#
#   ./install.sh           # symlink the skill into ~/.claude/skills (recommended for dev)
#   ./install.sh --copy    # copy the skill instead of symlinking
#   ./install.sh --uninstall
#
# After installing, restart Claude Code (or start a new session) so it's discovered.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO_DIR/skills/educational-video"
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DEST="$SKILLS_DIR/educational-video"

c_ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
c_info() { printf '\033[1;34m•\033[0m %s\n' "$*"; }
c_warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }

[[ -d "$SRC" ]] || { c_warn "skill not found at $SRC"; exit 1; }

if [[ "${1:-}" == "--uninstall" ]]; then
  if [[ -L "$DEST" || -e "$DEST" ]]; then
    rm -rf "$DEST"; c_ok "removed $DEST"
  else
    c_info "nothing to remove at $DEST"
  fi
  exit 0
fi

mkdir -p "$SKILLS_DIR"

# Refuse to clobber an unrelated real directory; allow replacing our own link/copy.
if [[ -e "$DEST" && ! -L "$DEST" ]]; then
  c_warn "$DEST already exists (not a symlink). Remove it first, or run with --copy after deleting."
  exit 1
fi
[[ -L "$DEST" ]] && rm -f "$DEST"

if [[ "${1:-}" == "--copy" ]]; then
  cp -r "$SRC" "$DEST"
  c_ok "copied skill to $DEST"
else
  ln -s "$SRC" "$DEST"
  c_ok "symlinked $DEST -> $SRC"
fi

# Friendly dependency check (non-fatal — the skill bootstraps what's missing).
c_info "checking host tools (each video project installs its own Manim, Remotion, Playwright + Chromium and Piper on first run):"
for t in uv node npm ffmpeg ffprobe; do
  if command -v "$t" >/dev/null 2>&1; then c_ok "$t"; else c_warn "$t missing (required)"; fi
done
for t in pdflatex dvisvgm; do
  if command -v "$t" >/dev/null 2>&1; then c_ok "$t"; else c_warn "$t missing (only needed for Manim LaTeX)"; fi
done
if command -v node >/dev/null 2>&1; then
  major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  [[ "$major" -ge 22 ]] || c_warn "node $major found; the motion engine and the repo tests want Node 22 or newer"
fi

echo
c_ok "Installed. Restart Claude Code, then ask: \"make a video explaining <topic>\""
