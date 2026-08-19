# Troubleshooting

## Python / Manim

- **Manim won't install or import on system Python.** The system has Python 3.14, on which
  Manim's dependency chain (e.g. `dearpygui`) lacks wheels (ManimCommunity/manim#4459). **Always
  use the uv-managed Python 3.12 venv** created by `bootstrap.sh` (`uv venv --python 3.12 .venv`)
  and invoke Manim as `.venv/bin/manim`. Never `pip install manim` into system Python.
- **`uv python install 3.12` needed.** If the pinned interpreter isn't present, bootstrap runs
  `uv python install 3.12` first.
- **`ModuleNotFoundError: manim`** → you're using the wrong interpreter; use `.venv/bin/manim`
  (render.sh already does).

## LaTeX (Manim math)

- **`LaTeX Error` / `dvisvgm` failure.** Check the TeX string (use raw strings `r"..."`, balanced
  braces). The system has TeX Live 2025 + `dvisvgm`. For uncommon packages, set a custom
  `TexTemplate` and `add_to_preamble(r"\usepackage{...}")`. Missing packages: install via
  `tlmgr install <pkg>` (or the distro's texlive-extra packages).
- **Equation shows as plain text** → use `MathTex`/`Tex`, not `Text`.

## Cairo / Pango

- Present on this machine. If text rendering errors mention pango/cairo, confirm
  `libcairo2`/`libpango` are installed (they are) and that the venv's `manimpango` wheel built.

## Remotion / Chrome

- **Chrome Headless Shell missing / launch fails.** Run `npx remotion browser ensure` (bootstrap
  pre-warms this). On minimal Linux you may need libs: `libnss3 libatk1.0-0 libgbm1 libasound2`
  (install via apt if a render complains about a missing `.so`).
- **`Composition "X" not found`** → register it in `src/Root.tsx`.
- **OOM during render** → lower `--concurrency` (e.g. `--concurrency=2`) and render scenes one at
  a time.

## ffmpeg / mux

- **Concat fails / glitches at joins** → use the concat *demuxer* with a file list and ensure all
  scenes share codec/fps/resolution (they do if rendered with the same settings). `mux.sh`
  re-encodes if params differ.
- **Audio/video out of sync** → ensure each scene's video duration ≥ its audio; the Phase-9
  reconciliation extends short scenes. Use `-af loudnorm` for consistent volume.
- **Subtitles not showing** → soft-muxed `.srt` needs a player with subtitles on; use the burned
  `.ass` path (`-vf subtitles=...`) if you need them always visible.

## Motion engine

- **`playwright not found`** → `scripts/bootstrap.sh <project> motion` (or `npm i -D playwright && npx playwright install chromium`
  inside the project); `render.mjs` resolves Playwright from the project folder.
- **Chromium does not start** → on a minimal Linux box install its shared libraries (`npx playwright install-deps chromium`).
- **`the film failed to load`** → the message is the page error. `unknown mark or cue "x"` means a typo in `film.js` or
  `timeline.json`, or a cue that `grid.json` does not define; fix the name and re-run `sync.mjs`.
- **`NOT DETERMINISTIC at t=...`** (`--verify`) → state leaks between frames: a CSS transition, `setTimeout`, `will-change`,
  CSS 3D, `Math.random`, or a variable mutated in `run()`. See `motion-rules.md`.
- **`Unable to capture screenshot`** → occasional headless Chromium refusal; `render.mjs` retries each capture four times.
  If it persists, close other heavy browsers and re-run.
- **`font not loaded`** in the `[page]` log → the face named in `C.fonts` has no `@font-face` in `film/index.html`; the system
  stack is used meanwhile.
- **Stale engine copy** → a project keeps the engine files it was scaffolded with; `scripts/scaffold_motion.sh <project> --update`
  refreshes them without touching `film.js`, `timeline.json` or `data.js`.
- **Renders are slow** → finals do adaptive motion blur (2-24 screenshots per frame). Iterate with `low` (30 fps, no blur)
  or contact sheets, render `high` once.

## TTS

- **No cloud key** → Piper is used; if Piper binary/model download failed, bootstrap falls back
  to `espeak-ng`. Set `ELEVENLABS_API_KEY`/`OPENAI_API_KEY` for better voices.
- **No word timestamps** → Phase 8 installs `faster-whisper` and force-aligns.

## General

- Every phase writes state to `manifest.json`; if a run dies, re-invoke the skill — it resumes
  from the last incomplete phase.
- If cumulative re-renders hit the 40 cap, the run delivers best-effort and lists unresolved
  warnings — inspect `.videogen/critic/` and `.videogen/logs/`.
