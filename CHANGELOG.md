# Changelog

## 2.0.0

A rewrite of the skill around one narration clock, a third engine and a scored critic.

### Added

- **Motion engine** (`engines/motion/`): a `seek(t)` HTML film rendered frame by frame with
  Playwright and ffmpeg (adaptive motion blur, determinism check), closed-form springs, a time
  source in seconds with marks and narration cues, per-format re-blocking (`C.pick`), and lesson
  components: KaTeX equations (vendored, offline) with per-term reveal, highlighted code with
  typing and line focus, plots, diagrams and algorithm stepping, word-synced captions.
- **Narration grid**: `grid.py` turns word timings (ElevenLabs, or faster-whisper alignment of
  Piper/OpenAI audio) into scene slots and named cues (`s03.derivative`); storyboard beats can
  anchor to a word with `"on"`. Scene lengths come from real speech.
- **Sound**: `music.py` (seeded quiet bed: calm, curious, upbeat), `sfx.mjs` (pop, click, tick,
  whoosh, chime, thump on cues), `mix.py` (side-chain ducking, -14 LUFS, true peak <= -1 dBTP).
- **Springs everywhere**: `springs.py` and `springs.ts` give Manim and Remotion the same four
  spring presets as the motion engine, checked against a reference implementation in the tests.
- **Formats**: 16x9, 1x1, 4x5 and 9x16 in all engines, with 9:16 safe zones; soft subtitles, or
  burned-in captions in 9:16. `mux.sh --format all`.
- **Presets**: `blank`, `chalkboard`, `paper`, `blueprint` (palette, two OFL fonts, voice, music
  mood, caption style), applied to Manim, Remotion and motion projects by `apply_preset.py`.
- **Shorts**: `mode: "short"` storyboards (30-60 s, 9:16, hook within 3 s), a template,
  `new_project.sh --short`, `references/shorts.md`.
- **Scored critic**: `review.py` builds contact sheets, fast-action strips, phone sheets, a 9:16
  safe-zone sheet and `metrics.json` from the rendered files of any engine; `critique.md` scores 8
  criteria with automatic caps. Strict by default (3+ rounds, all >= 8), `--quick` for one round at >= 7.
- Storyboard schema v2 (`mode`, `formats`, `preset`, `engine: motion`, beat `on`); v1 storyboards still validate.
- Tests (`node --test`, pytest) and CI; `examples/` with a lesson and a short.

### Changed

- `SKILL.md` is organised as phases 0-10 with an approval stop after the storyboard; narration
  comes before code.
- `render.sh`, `extract_frames.sh` and `mux.sh` take a format. Finals are `final.mp4` (first
  format) and `final_<fmt>.mp4`.
- `bootstrap.sh` also installs Piper with a voice, faster-whisper, numpy, scipy and Pillow, and
  for motion Playwright and Chromium.
- Preset voice, music mood and levels, and the sfx switch are honoured by `tts.py`, `music.py`
  and `mix.py`; the motion engine takes the preset's colours and fonts and the storyboard's formats.

### Fixed

- The motion film rendered the timeline's formats instead of the storyboard's; `cues.json` was
  written empty and blocked the sfx plan; the critic did not find a primary `final.mp4` next to
  `final_<fmt>.mp4`; `gridsync` was never copied into Manim/Remotion projects.
- `uv.lock` is no longer tracked. CI runs on Node 22 and 24 so the TypeScript parity tests run.
