# Educational Video Generator

A **Claude Code skill** that turns a topic into a narrated, captioned **educational video** or a
vertical **short**, by writing and rendering code (Manim, Remotion or a spring-driven motion
engine) instead of generating pixels. Built for math, physics, CS and algorithm explainers
where an equation or a number on screen has to be right.

Version 2.0.0. See `CHANGELOG.md`.

## Why code, not text-to-video

Text-to-video models cannot hold logical, numeric or textual rigor: equations drift and labels
are wrong. Here the model writes the storyboard and the animation code, a renderer produces the
frames, and a critic looks at the *rendered* output and decides what to fix. Every number on screen is the
one in the storyboard.

## What you get

```
topic or script
  -> storyboard.json  (you approve it)
  -> narration (Piper, or ElevenLabs / OpenAI) -> one word-level grid with named cues
  -> code in Manim | Remotion | motion, placed on the cues
  -> render loop (error retries, frame checks, determinism check)
  -> music bed + sound effects + mix at -14 LUFS
  -> scored critic rounds on the rendered files (8 criteria, caps, evidence)
  -> final.mp4 (+ 9:16, 1:1, 4:5), soft subtitles or burned-in captions
```

- **Three engines.** Manim for math and geometry, Remotion for UI/data/branded work, and the
  **motion engine** (HTML + closed-form springs, rendered frame by frame with Playwright) for
  concept explainers, algorithm stepping, kinetic type and shorts. It ships lesson components:
  KaTeX equations revealed term by term, highlighted code, plots, diagrams and word-synced captions.
- **Picture and sound on one clock.** Scene lengths and every animation come from the spoken
  words, so things appear as they are said.
- **Looks and formats.** Presets (`chalkboard`, `paper`, `blueprint`, `blank`) with OFL fonts;
  16:9, 1:1, 4:5 and 9:16, re-blocked per format with the 9:16 safe zones respected.
- **Shorts.** 30-60 s vertical micro-lessons with a hook inside three seconds.
- **Offline by default.** Piper speaks, no API key needed; a key unlocks better voices.

## Install

Requirements: `uv`, Node.js 22+, `ffmpeg`; for Manim also `pdflatex` + `dvisvgm`, cairo and
pango. Everything else is installed into each project folder on first use.

```bash
git clone <this repository>
cd educational-video-generator
./install.sh            # symlink the skill into ~/.claude/skills (--copy to copy, --uninstall)
```

Restart Claude Code, then ask for a video. `install.sh` checks the host tools (Node 22+ for the
motion engine's Playwright, ffmpeg, uv, LaTeX) and tells you what is missing. The motion
engine's npm dependencies (Playwright, Chromium) and Piper are installed per project by the
skill's `bootstrap.sh`.

## Use

- "Make a 2-minute video explaining why e^(i*pi) = -1"
- "Animate how binary search works, chalkboard look, with a 9:16 version"
- "Make a 45 second short on why the sum of odd numbers is a square"
- "Add narration and captions to this animation"

The skill asks two or three questions, writes the storyboard and **waits for your approval**
before spending render time. Add "quick" for a one-round review. Re-invoking resumes the run.
Worked storyboards are in `examples/`: `odd-squares.storyboard.json` (a lesson) and
`halving.storyboard.json` (a short).

## Repository

```
install.sh   CHANGELOG.md   examples/   tests/   .github/workflows/ci.yml
skills/educational-video/   SKILL.md  README.md  references/  engines/motion/  presets/  templates/  scripts/
```

`skills/educational-video/README.md` describes the skill's contents and the project layout.

## Development

```bash
npm test                                                    # node --test tests/node (Node >= 22.18)
uv run --with pytest --with numpy --with pillow --with scipy --with soundfile pytest tests/py
uvx --from shellcheck-py shellcheck -x install.sh skills/educational-video/scripts/*.sh
```

CI runs the same on Node 22 and 24 and Python 3.10 and 3.12. The tests do not render video,
apart from tiny synthetic clips for the critic metrics, the mixer and the muxer.

## Scope

Code-driven only. Text-to-video, avatar models and product-site capture are out of scope.

## Third-party files

The bundled preset fonts are SIL OFL (licence texts sit next to them in `presets/*/fonts/`) and
KaTeX is MIT (`engines/motion/vendor/katex/LICENSE`).
