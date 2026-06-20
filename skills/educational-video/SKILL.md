---
name: educational-video
description: >-
  Use when the user wants to create, generate, or produce an educational or explainer
  video, animated lesson, math/physics/CS visualization, algorithm or data-structure
  walkthrough, tutorial or lecture clip, or narrated whiteboard-style explainer — including
  asks like "make a video explaining X", "animate this concept", "turn this script/lesson
  into a video", "Manim video", "Remotion video", "3Blue1Brown-style animation", or any
  request for a rendered MP4 that teaches a topic with visuals plus voiceover and subtitles.
  Also use when the user wants to add narration, TTS voiceover, or word-aligned captions to
  a generated animation.
---

# Educational Video Generator

Generate high-quality, consistent educational videos by **writing and rendering code**, not
by synthesizing pixels. Diffusion/text-to-video models (Sora, Veo, Runway, Kling) cannot
hold logical, numeric, or textual rigor and score poorly on educational content. The reliable
approach is **code-driven + agentic**: a Planner writes a storyboard, a Coder writes Manim
(Python) or Remotion (React/TSX) code, a renderer executes it, and a vision Critic inspects
the rendered frames and drives fixes — looping until each scene passes.

## Operating principle

You (Claude Code) play three roles across the pipeline. Switch deliberately and say which hat
you're wearing:

- **Planner** — turns the topic/script into a schema-valid `storyboard.json`.
- **Coder** — turns each storyboard scene into executable, *debuggable* engine code, grounded
  in `references/manim-patterns.md` / `references/remotion-patterns.md` (read the relevant
  patterns BEFORE writing code — this doc-grounding is what raises render success to ~94%).
- **Critic** — reads rendered frames as images and judges layout, legibility, timing.

Two agentic loops do the heavy lifting (full spec in `references/verify-loop.md`):
1. **RITL** (Renderer-in-the-Loop): render → on error, retrieve the failing-symbol doc snippet,
   patch minimally, re-render. Max **5** render-error retries per scene → hard fail, escalate.
2. **Vision critic**: extract beat frames → Read() them → fix issues → re-render. Max **3**
   critic-fix passes per scene → soft fail, warn and continue.

Global guardrail: cap cumulative re-renders at **40 per run**; if hit, deliver best-effort and
report. Keep `manifest.json` updated after every phase so a re-invocation resumes mid-pipeline.

## Phase pipeline

Work through these in order. Read `manifest.json` first; skip any phase already marked done.

### Phase 0 — Intake
Capture: topic (or supplied script), target duration, audience level, aspect ratio
(default **16:9, 1920x1080, 30fps**), narration on/off, voice/language. Ask at most **2–3**
clarifying questions, then proceed. If the user gave a script, ingest it; if only a topic, the
Planner writes the script in Phase 3.

### Phase 1 — Bootstrap (idempotent)
Run `scripts/bootstrap.sh <project-dir> <engine|auto>`. It detects what's present and installs
only what's missing: a **uv-managed Python 3.12 venv** (never system Python — Manim breaks on
3.14), Manim, a Remotion scaffold, and TTS. Then run `scripts/detect_tts.py` and write results
to `<project>/.videogen/env.json`. If Manim install fails, set engine=remotion in the manifest
with the reason and continue. See `references/troubleshooting.md` for failures.

### Phase 2 — Engine selection
Score the content: **math/geometric/numeric rigor** vs **web/text/design/UI**. Higher wins.
Tie-break: STEM → **Manim**, else **Remotion**. Write `engine` + `engine_reason` to the
manifest. The user may override. Heuristics: `references/engine-selection.md`.

### Phase 3 — Plan / storyboard (Planner)
Create `storyboard.json` per `references/storyboard-schema.md`: decompose into scenes, each with
`narration`, `elements`, animation `beats` (with timestamps), `est_duration_s`, `template`,
`assets`. Validate with `scripts/validate_storyboard.py`; fix until it passes. Summed scene
durations must be within **±15%** of target.

### Phase 4 — Generate code (Coder)
For each scene, FIRST read the matching patterns + component templates
(`references/component-library.md`), THEN write code. Prefer instantiating templates
(TitleCard, BulletList, EquationReveal, CodeBlock, DataChart, LowerThird, SceneTransition) over
raw animation — templates encode safe-area margins, font sizes, and a consistent palette, which
prevents most critic failures.
- Manim → `scenes/scene_<id>.py` (one `Scene` subclass per storyboard scene).
- Remotion → `scenes/Scene<Id>.tsx`, registered in `src/Root.tsx`.

### Phase 5 — Render
Render per scene first (fast iteration): `scripts/render.sh <engine> <project> <scene> <quality>`
(use medium quality while iterating, high for the final pass). Capture exit code + stderr to
`.videogen/logs/scene_<id>.render.log`.

### Phase 6 — Verify (core loop, per scene)
Apply `references/verify-loop.md`:
1. **RITL**: if render exit ≠ 0, parse the error, retrieve the relevant doc snippet for the
   failing symbol, apply a minimal patch, re-render (≤5). On exhaustion, escalate with the log.
2. **Vision critic**: extract beat frames via `scripts/extract_frames.sh`, Read() each as an
   image, evaluate the rubric (overlap / off-screen safe-area / legibility incl. LaTeX rendered
   / composition / beat-timing). On FIX, give the Coder targeted instructions, re-render,
   re-critique (≤3). PASS = exit 0 AND critic PASS.

### Phase 7 — Narration / TTS
If narration is on, run `scripts/tts.py <project>` to synthesize per-scene audio from each
scene's `narration` text using the provider resolved in Phase 1 (cloud if a key is set, else
local Piper). Output `audio/scene_<id>.wav` + `audio/scene_<id>.words.json` (word timestamps
where the provider supports them). See `references/tts-setup.md`.

### Phase 8 — Subtitle alignment
Run `scripts/align_subtitles.py <project>`: use provider word-timings directly, else force-align
(faster-whisper, installed lazily). Output `output/subtitles.srt` + styled `output/subtitles.ass`.

### Phase 9 — Mux
Run `scripts/mux.sh <project>`: concat scene videos, attach narration, normalize loudness
(`loudnorm`), soft-mux subtitles → `output/final.mp4`. If a scene's animation is shorter than
its narration, extend that scene's duration in code and re-render (≤2 reconciliation passes).

### Phase 10 — Deliver
Report the path to `output/final.mp4`, total duration, engine used, per-scene retry counts, and
any unresolved critic warnings.

## Resumability & state

- `scripts/new_project.sh <slug>` creates the per-run scaffold (`manifest.json`,
  `storyboard.json` stub, `.videogen/`, `scenes/`, `assets/`, `audio/`, `output/`).
- Treat `manifest.json` as the single source of run state; update `phase`, `engine`, retry
  counts, TTS provider, and warnings as you go.
- `storyboard.json` is the contract between Planner and Coder — you can re-render the same
  storyboard with the other engine.

## Scope (v1)

- Mixed-engine single video is allowed but discouraged; record it as a known limitation.
- AI text-to-video (Sora/Veo) and avatar tools (HeyGen/Synthesia) are **out of scope** — they
  hurt educational rigor. They're noted in references as optional B-roll/presenter add-ons only.

## Reference index

- `references/engine-selection.md` — Manim vs Remotion heuristics + scoring.
- `references/storyboard-schema.md` — `storyboard.json` schema + examples.
- `references/manim-patterns.md` — Manim API snippets + error→fix table (RITL-DOC corpus).
- `references/remotion-patterns.md` — Remotion API snippets + error→fix table (RITL-DOC corpus).
- `references/component-library.md` — reusable templates for both engines.
- `references/verify-loop.md` — RITL + vision-critic rubric, frame sampling, retry caps.
- `references/tts-setup.md` — provider detection, recipes, alignment fallback.
- `references/troubleshooting.md` — Python 3.14/Manim, LaTeX, cairo/pango, ffmpeg, Chrome shell.
