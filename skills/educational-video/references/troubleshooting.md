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
- **Audio/video out of sync** → scene videos must match their slot in `grid.json`. `mux.sh`
  holds the last frame of a short render and trims a long one, and warns when the gap is large:
  end Manim scenes with `self.finish()`, size Remotion compositions with `sceneFrames(id)`.
  After changing narration, re-run `tts.py`, `grid.py` and re-render; the grid is the clock.
- **Loudness off target** → never use `loudnorm` per scene; `mix.py` masters the whole mix to
  -14 LUFS / -1 dBTP once (`audio.md`). A `WARNING: off target` means lower the loudest stem.
- **Subtitles not showing** → soft-muxed `.srt` needs a player with subtitles on; use the burned
  `.ass` path (`-vf subtitles=...`) if you need them always visible.

## TTS

- **No cloud key** → Piper is used; if Piper binary/model download failed, bootstrap falls back
  to `espeak-ng`. Set `ELEVENLABS_API_KEY`/`OPENAI_API_KEY` for better voices.
- **No word timestamps** → `grid.py` force-aligns with `faster-whisper` (installed by bootstrap
  with Piper, or lazily). If it fails it prints a warning and estimates word times from text
  length: anchors still resolve but land less precisely. Fix the install and re-run `grid.py`.
- **`TypeError ... metadata_errors` from faster-whisper** → an old PyAV; `grid.py` decodes audio
  with ffmpeg itself, so make sure it is the current script.
- **`anchor ... says "x" 0 time(s)` / "not in scene"** → the beat's `on` word is not in that scene's
  narration (or the narration changed); fix the word or use `wN` / `pN`. List cues with
  `python3 -c "import json;print(*json.load(open('grid.json'))['cues'])"`.

## General

- Every phase writes state to `manifest.json`; if a run dies, re-invoke the skill — it resumes
  from the last incomplete phase.
- If cumulative re-renders hit the 40 cap, the run delivers best-effort and lists unresolved
  warnings — inspect `.videogen/critic/` and `.videogen/logs/`.
