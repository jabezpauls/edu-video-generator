# educational-video

Version 2.0.0 (see `CHANGELOG.md` at the repository root).

A Claude Code skill that makes narrated educational videos by writing and rendering code, in
three engines, with one narration clock, a mixed soundtrack and a scored critic. Ask for a
lesson ("explain why e^(i*pi) = -1", "animate binary search") or a short ("a 45 second short
on how a hash table works") and it plans, narrates, animates, mixes and reviews, then hands you
`final.mp4` (and a 9:16 version when you want one).

## What is in it

- **Three engines.** Manim (math, geometry), Remotion (UI, data, branded), and **motion**, a
  spring-driven `seek(t)` HTML engine rendered by Playwright, with ready-made lesson components
  (KaTeX equations with per-term reveal, highlighted code, plots, diagrams and algorithm
  stepping, word-synced captions). Pick per topic; the storyboard is the same for all.
- **One narration grid.** Text-to-speech (ElevenLabs, OpenAI, or offline Piper) gives word times;
  `grid.py` turns them into scene lengths and named cues (`s03.derivative`). Animations and
  sound effects are placed on those cues, so picture and voice agree to well under 80 ms.
- **Sound.** A quiet seeded music bed (calm, curious, upbeat), sound effects on the cues, a
  side-chain ducked mix mastered to -14 LUFS with true peak below -1 dBTP.
- **Formats.** 16:9, 1:1, 4:5 and 9:16, re-blocked per format rather than cropped, with the
  9:16 platform safe zones. Soft subtitles, or word-synced burned-in captions in 9:16.
- **Looks.** `chalkboard`, `paper`, `blueprint` presets (palette, two OFL fonts, voice, music
  mood, caption style) plus a documented `blank` to make your own.
- **Shorts.** 30-60 s micro-lessons: a hook inside 3 seconds, one idea, a payoff; validated
  by the storyboard checker, motion engine by default.
- **A critic that can say no.** `review.py` builds contact sheets, fast-action strips, phone
  sheets and metrics from the *rendered files*; the critic scores 8 criteria with caps and
  evidence. Strict default (3+ rounds, every score >= 8) or `--quick` (1 round, >= 7).

## Using it

Ask in plain language. The skill asks two or three questions (audience, length, lesson or
short, format, look), writes `storyboard.json`, **stops for your approval**, then does the
rest and reports the paths, durations, loudness and critic scores. Re-invoking resumes from
`manifest.json`. The phases are in `SKILL.md`; the scripts are plain CLIs you can run yourself:

```bash
S=~/.claude/skills/educational-video
$S/scripts/new_project.sh ~/videos halving motion --short       # scaffold a 9:16 short
$S/scripts/bootstrap.sh ~/videos/halving motion                  # venv, Piper, Playwright
python3 $S/scripts/validate_storyboard.py ~/videos/halving
```

For better voices export `ELEVENLABS_API_KEY` or `OPENAI_API_KEY` first; otherwise Piper runs
locally with no key.

## Requirements

`uv`, Node.js 22+ and npm, `ffmpeg`/`ffprobe`. For Manim also a LaTeX toolchain (`pdflatex`,
`dvisvgm`) and cairo/pango. Everything else (a pinned Python 3.12 venv, Manim, Remotion,
Playwright and Chromium, Piper and a voice, numpy/scipy/Pillow, faster-whisper for word
alignment) is installed by `bootstrap.sh` the first time, into the project folder.

## Layout

```
SKILL.md                orchestration: phases 0-10, roles, loops, critic rules
references/             read on demand
  engine-selection.md   storyboard-schema.md   shorts.md
  motion-engine.md      motion-components.md   motion-rules.md
  manim-patterns.md     remotion-patterns.md   component-library.md
  formats.md            presets.md             audio.md      tts-setup.md
  verify-loop.md        critique.md            troubleshooting.md
engines/motion/         the motion engine: core, type, springs, time, lesson components, vendored KaTeX
presets/                blank, chalkboard, paper, blueprint (+ OFL fonts and licences)
templates/              springs/formats/gridsync for Manim and Remotion, timeline.json, review_log.md,
                        short.storyboard.json
scripts/
  new_project.sh bootstrap.sh detect_tts.py validate_storyboard.py   set up and plan
  tts.py grid.py wordtimes.py align_subtitles.py                      narration, grid, subtitles
  music.py sfx.mjs mix.py projectcfg.py                               sound
  apply_preset.py scaffold_engine.sh scaffold_motion.sh               looks and engine helpers
  sync.mjs render.mjs render.sh extract_frames.sh mux.sh              render and assemble
  review.py                                                           critic kit
```

## A project folder

```
<slug>/
  manifest.json storyboard.json grid.json cues.json preset.json
  audio/        scene_<id>.wav  music.wav  sfx.wav  mix.wav  mix_report.json
  scenes/       (Manim, Remotion)        film/ timeline.json  (motion)
  output/       final.mp4  final_<fmt>.mp4  subtitles.srt  subtitles*.ass
  renders/      raw motion renders       review/ r<N>/ sheets + metrics.json
  docs/         review_log.md            .videogen/ logs, frames, env
```

## Limits

Code-driven only: no text-to-video or avatar models. A motion lesson is authored in JavaScript
against the component API; heavy LaTeX derivations and geometric constructions are still
Manim's job. English narration is the tested path. One engine per video.
