# educational-video

A Claude Code skill that generates high-quality, consistent **educational** videos by writing
and rendering **code** (Manim or Remotion) inside an agentic render-verify loop — rather than
synthesizing pixels with text-to-video models, which can't hold logical/numeric/text rigor.

## What it does

Topic or script → engine selection → storyboard → per-scene code → render → **RITL** error loop
+ **vision-critic** layout review → TTS voiceover → word-aligned subtitles → muxed `final.mp4`.

Based on verified research (Code2Video tri-agent Planner/Coder/Critic; Renderer-in-the-Loop with
doc-grounded retries raising render success to ~94%).

## How to use

Just ask, e.g.:
- "Make a 2-minute video explaining why e^(iπ) = −1"
- "Turn this lesson script into an animated explainer with narration"
- "Animate how binary search works"

Claude Code will invoke this skill and walk the phases in `SKILL.md`, asking 2–3 clarifying
questions, then bootstrapping and producing the video in a project folder under your workspace.

## Requirements

Present on this machine: `uv`, Python 3.14 (a pinned **3.12** venv is created for Manim — 3.14
breaks Manim), Node/npm, ffmpeg, LaTeX (pdflatex+dvisvgm), cairo, pango.

Installed on first run as needed: Manim (pip into the venv), Remotion (npm), TTS.

**Narration quality:** with no cloud key set, narration uses local **Piper** (offline). For
better voices, set `ELEVENLABS_API_KEY` or `OPENAI_API_KEY` before running.

## Layout

```
SKILL.md                  # orchestration: phases, agent roles, loops, retry caps
references/               # knowledge corpus (read on demand)
  engine-selection.md     # Manim vs Remotion heuristics
  storyboard-schema.md    # storyboard.json contract
  manim-patterns.md       # Manim snippets + error→fix table
  remotion-patterns.md    # Remotion snippets + error→fix table
  component-library.md     # reusable templates (both engines)
  verify-loop.md          # RITL + vision-critic rubric
  tts-setup.md            # provider detection + recipes
  troubleshooting.md      # known failure modes + fixes
scripts/                 # deterministic helpers
  bootstrap.sh            # env setup (uv venv 3.12, Manim, Remotion, TTS)
  detect_tts.py           # resolve TTS provider → JSON
  new_project.sh          # per-run scaffold + manifest/storyboard stubs
  validate_storyboard.py  # storyboard validation
  render.sh               # unified render (manim|remotion)
  extract_frames.sh       # critic frames (ffmpeg / remotion still)
  tts.py                  # per-scene narration synthesis
  align_subtitles.py      # .srt/.ass from word timings or forced alignment
  mux.sh                  # concat + audio + loudnorm + subtitles → final.mp4
```

## Per-run output

Created under your working dir as `<slug>/`: `manifest.json` (resumable run state),
`storyboard.json`, `scenes/`, `audio/`, `output/{scene_*.mp4,subtitles.*,final.mp4}`, and a
`.venv/` for Manim. Re-invoking the skill resumes from the last incomplete phase.

## Scope (v1)

Code-driven only. AI text-to-video (Sora/Veo) and avatars (HeyGen/Synthesia) are out of scope —
noted as optional B-roll/presenter add-ons but not depended on.
