# Educational Video Generator

> A **Claude Code skill** that turns any topic into a narrated, subtitled **educational video** —
> using **code-driven animation** (Manim + Remotion) inside an agentic *render → verify → fix*
> loop. Built for math, physics, CS, and algorithm explainers where correctness matters.

Keywords: educational video generation · AI video generator · Manim · Remotion · Claude Code
skill · text-to-video alternative · explainer videos · 3Blue1Brown-style animation.

---

## Why code-driven (not text-to-video)?

End-to-end text-to-video models (Sora, Veo, Runway, Kling) score poorly on **educational**
content — they can't hold logical, numeric, or textual rigor (equations drift, labels are wrong).
This skill instead has the LLM **write and render code**, then a vision **critic** inspects the
rendered frames and drives fixes. Based on the verified research pattern (Code2Video tri-agent
Planner/Coder/Critic + Renderer-in-the-Loop with doc-grounded retries → ~94% render success).

## What you get

Ask in plain language → the skill produces a finished `final.mp4`:

```
topic / script
   └─► engine selection (Manim vs Remotion)
        └─► storyboard.json
             └─► per-scene code  ──► render ──► RITL error loop + vision critic
                                                      └─► TTS voiceover ──► word-aligned subtitles
                                                                              └─► muxed final.mp4
```

- **Two co-equal engines:** Manim (Python — math/geometry/algorithms) and Remotion (React/TSX —
  UI/text/data/branded explainers), auto-selected per topic.
- **Full pipeline:** visuals + voiceover + subtitles, muxed and loudness-normalized.
- **Self-correcting:** deterministic error retries + a vision critic that catches overlap,
  off-screen, illegible text, and bad timing.
- **Per-run TTS:** uses ElevenLabs/OpenAI if a key is set, else local **Piper** (offline).
- **Auto-bootstrap:** creates a project scaffold + a pinned Python 3.12 venv and installs what's
  missing on first run.

## Install

**Requirements:** `uv`, Node.js + npm, `ffmpeg`, and (for Manim math) a LaTeX toolchain
(`pdflatex` + `dvisvgm`), plus cairo/pango. Manim, Remotion, and TTS are installed automatically
on first run.

```bash
git clone https://github.com/<your-username>/educational-video-generator.git
cd educational-video-generator
./install.sh            # symlink the skill into ~/.claude/skills (use --copy to copy instead)
```

`install.sh` links `skills/educational-video` into `~/.claude/skills/`, making it available to
Claude Code. Restart Claude Code (or start a new session) and the skill is discoverable.

> Manual install: copy or symlink `skills/educational-video/` into `~/.claude/skills/`.

## Usage

Just ask Claude Code naturally:

- *"Make a 2-minute video explaining why e^(iπ) = −1"*
- *"Turn this lesson script into an animated explainer with narration"*
- *"Animate how binary search works"*
- *"Create a Remotion video walking through this API"*

The skill asks 2–3 clarifying questions (duration, audience, narration), then bootstraps and
produces the video in a project folder under your working directory. Re-invoking resumes from the
last incomplete phase (state lives in `manifest.json`).

**Better narration (optional):** set `ELEVENLABS_API_KEY` or `OPENAI_API_KEY` before running for
higher-quality voices; otherwise local Piper is used.

## Repository structure

```
educational-video-generator/
├── README.md                 # you are here
├── install.sh                # link/copy the skill into ~/.claude/skills
├── .gitignore
└── skills/
    └── educational-video/
        ├── SKILL.md          # orchestration: phases, agent roles, loops, retry caps
        ├── README.md         # skill-specific docs
        ├── references/       # knowledge corpus (engine selection, schemas, patterns, verify loop, TTS, troubleshooting)
        └── scripts/          # bootstrap, render, frame-extract, TTS, subtitle align, mux
```

## How it works (the loops)

- **RITL (Renderer-in-the-Loop):** render → on error, retrieve the failing-symbol doc snippet →
  minimal patch → re-render (≤5 tries/scene).
- **Vision critic:** extract beat frames → read them as images → check overlap / safe-area /
  legibility (incl. LaTeX rendered) / composition / timing → route targeted fixes (≤3 passes).
- **Guardrails:** ≤40 cumulative re-renders/run, ≤6 critic frames/scene; soft-fail keeps best
  effort and reports warnings.

## Scope

Code-driven only (v1). AI text-to-video (Sora/Veo) and avatar tools (HeyGen/Synthesia) are out of
scope — they reduce educational rigor — but are noted as optional B-roll/presenter add-ons.

## Suggested GitHub topics

`claude-code` · `claude-skill` · `educational-video` · `video-generation` · `manim` · `remotion`
· `text-to-video` · `ai-video` · `explainer-videos` · `animation`
