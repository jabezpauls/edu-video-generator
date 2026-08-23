---
name: educational-video
description: >-
  Use when the user wants to create, generate, or produce an educational or explainer
  video, animated lesson, math/physics/CS visualization, algorithm or data-structure
  walkthrough, tutorial or lecture clip, or narrated whiteboard-style explainer — including
  asks like "make a video explaining X", "animate this concept", "turn this script/lesson
  into a video", "Manim video", "Remotion video", "3Blue1Brown-style animation", or any
  request for a rendered MP4 that teaches a topic with visuals plus voiceover and subtitles,
  including spring-animated concept explainers, algorithm walkthroughs and kinetic-type lessons.
  Also use when the user wants to add narration, TTS voiceover, or word-aligned captions to
  a generated animation.
---

# Educational Video Generator

Generate high-quality, consistent educational videos by **writing and rendering code**, not
by synthesizing pixels. Diffusion/text-to-video models (Sora, Veo, Runway, Kling) cannot
hold logical, numeric, or textual rigor and score poorly on educational content. The reliable
approach is **code-driven + agentic**: a Planner writes a storyboard, a Coder writes Manim
(Python), Remotion (React/TSX) or motion-engine (seek(t) HTML/JS) code, a renderer executes it, and a vision Critic inspects
the rendered frames and drives fixes — looping until each scene passes.

## Operating principle

You (Claude Code) play three roles across the pipeline. Switch deliberately and say which hat
you're wearing:

- **Planner** — turns the topic/script into a schema-valid `storyboard.json`.
- **Coder** — turns each storyboard scene into executable, *debuggable* engine code, grounded
  in `references/manim-patterns.md` / `references/remotion-patterns.md` (read the relevant
  patterns / `references/motion-engine.md` BEFORE writing code — this doc-grounding is what raises render success to ~94%).
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
3.14), Manim, a Remotion scaffold, and TTS. With `auto` it only probes node + ffmpeg for the
motion engine; once the engine is chosen, `bootstrap.sh <project-dir> motion` scaffolds `film/`
and `timeline.json` and installs Playwright + Chromium (`new_project.sh <base> <slug> motion`
does the file scaffold alone). Then run `scripts/detect_tts.py` and write results
to `<project>/.videogen/env.json`. If Manim install fails, set engine=remotion in the manifest
with the reason and continue. See `references/troubleshooting.md` for failures.

### Phase 2 — Engine selection
Score the content on three axes: **math/geometric/numeric rigor** (→ Manim), **web/text/design/UI**
(→ Remotion) and **concept explainer / algorithm stepping / kinetic type / Shorts** (→ **motion**,
the spring-driven seek(t) engine). Highest wins. Tie-break: STEM → **Manim**, else **Remotion**. Write `engine` + `engine_reason` to the
manifest. The user may override. Heuristics: `references/engine-selection.md`.

### Phase 3 — Plan / storyboard (Planner)
Create `storyboard.json` per `references/storyboard-schema.md`: decompose into scenes, each with
`narration`, `elements`, animation `beats` (timestamps via `t`, or anchored to a spoken word
via `on`), `est_duration_s`, `template`, `assets`. Set `mode`, `formats` and `preset` only when
the user asked for them; the defaults are a 16x9 lesson. Validate with `scripts/validate_storyboard.py`; fix until it passes. Summed scene
durations must be within **±15%** of target.

### Phase 4 — Generate code (Coder)
With narration on, do Phase 7 first so scene lengths and `on` anchors come from `grid.json`.
For each scene, FIRST read the matching patterns + component templates
(`references/component-library.md`), THEN write code. Prefer instantiating templates
(TitleCard, BulletList, EquationReveal, CodeBlock, DataChart, LowerThird, SceneTransition) over
raw animation — templates encode safe-area margins, font sizes, and a consistent palette, which
prevents most critic failures.
- Manim → `scenes/scene_<id>.py` (one `Scene` subclass per storyboard scene).
- Remotion → `scenes/Scene<Id>.tsx`, registered in `src/Root.tsx`.
- Manim and Remotion get `springs`, `formats` and a preset `theme` in the project (`scripts/scaffold_engine.sh`,
  run by bootstrap; `scripts/apply_preset.py` re-applies a preset). Use them for motion, layout
  per format and colours/fonts: `references/formats.md`, `references/presets.md`.
- Motion → ONE film: `film/film.js` (a `scene()` per storyboard scene, named `s<id>`) plus the marks in
  `timeline.json`. Read `references/motion-engine.md` (API, time source) and `references/motion-rules.md`
  (springs only, determinism, lesson rhythm) first. Place things on marks/cues, not hard-coded seconds.

### Phase 5 — Render
Render per scene first (fast iteration): `scripts/render.sh <engine> <project> <scene> <quality>`
(use medium quality while iterating, high for the final pass). For Manim and Remotion add a format
(`16x9`, `1x1`, `4x5`, `9x16`, or `all` for every format in the storyboard) as a fifth argument to
render per format. Capture exit code + stderr to
`.videogen/logs/scene_<id>.render.log`. For `motion`, `render.sh motion <project> <id|all>
low|med|high` delegates to `scripts/render.mjs` (after re-syncing `timeline.json`); contact sheets
(`render.mjs --project <p> --sheet [--fmt 9x16]`) and stills (`--at 1.2,3.4`) are painted directly
from `seek(t)` in seconds, so use them for the first look before any video.

### Phase 6 — Verify (core loop, per scene)
Apply `references/verify-loop.md`:
1. **RITL**: if render exit ≠ 0, parse the error, retrieve the relevant doc snippet for the
   failing symbol, apply a minimal patch, re-render (≤5). On exhaustion, escalate with the log.
2. **Vision critic**: extract beat frames via `scripts/extract_frames.sh`, Read() each as an
   image, evaluate the rubric (overlap / off-screen safe-area / legibility incl. LaTeX rendered
   / composition / beat-timing). On FIX, give the Coder targeted instructions, re-render,
   re-critique (≤3). PASS = exit 0 AND critic PASS.
3. **Scored critic (after Phase 9, on the final MP4s)**: `scripts/review.py <round>` builds the
   critique kit, then a FRESH critic subagent scores 8 criteria using `references/critique.md`
   and appends to `docs/review_log.md`. Strict default: at least 3 rounds, ship when every score
   is ≥ 8. `--quick` (user asked for fast/draft): 1 round, ship at every score ≥ 7. After each
   round set `critic_rounds`, `scores` (latest round) and `critic_mode` in the manifest, fix the
   3 worst problems, re-render and repeat. Details: `references/verify-loop.md` §6.

### Phase 7 — Narration / TTS → narration grid
Narration is the clock. If narration is on, run it as soon as the storyboard is approved (before
coding scenes) and re-run after any script change:
`scripts/tts.py <project>` (per-scene audio from each scene's `narration`; cloud provider if a key
is set, else local Piper), then `scripts/grid.py <project> --write-durations` (word times, scene
slots from real speech, named cues in `grid.json`) and `scripts/grid.py resolve <project>`
(beat `on` anchors → times). Scenes read the grid with `templates/gridsync.py` (Manim) or
`templates/gridsync.ts` (Remotion), so animations land on their words and scenes are exactly as
long as their speech. See `references/tts-setup.md` and `references/audio.md`.

### Phase 8 — Subtitles and sound
`scripts/align_subtitles.py <project>` → `output/subtitles.srt` + `.ass` from the grid.
Then `scripts/grid.py cues <project>` and `node scripts/sfx.mjs <project>` (sound effects on
cues), `scripts/music.py <project> --mood curious|calm|upbeat|none` (bed), and
`scripts/mix.py <project>` (ducked, mastered to -14 LUFS, TP ≤ -1 dBTP → `audio/mix.wav`).

### Phase 9 — Mux
Run `scripts/mux.sh <project>`: conform each scene video to its grid slot, concat, attach
`audio/mix.wav` (remixing first if stale), soft-mux subtitles → `output/final.mp4`. If it warns
that a scene render is shorter or longer than its slot, fix the scene's timing and re-render
instead of relying on the hold/trim. A motion lesson is already one film:
`render.sh motion <project> all high` writes `output/final.mp4` (and `final_<fmt>.mp4` per extra
format) directly, and `render.mjs --mux` puts an existing `audio/mix.wav` into those renders.
Before delivery run `render.sh motion <project> all verify`: every probe frame must be identical.

### Phase 10 — Deliver
Report the path to `output/final.mp4`, total duration, engine used, per-scene retry counts, and
the final scores table (`manifest.json` `scores`, rounds in `docs/review_log.md`), and any
unresolved critic warnings.

## Resumability & state

- `scripts/new_project.sh <base-dir> <slug> [manim|remotion|motion]` creates the per-run scaffold
  (`manifest.json`, `storyboard.json` stub, `.videogen/`, `scenes/`, `assets/`, `audio/`, `output/`);
  with `motion` it also lays down `film/`, a starter `timeline.json` and `package.json`.
- Treat `manifest.json` as the single source of run state; update `phase`, `engine`, retry
  counts, TTS provider, and warnings as you go.
- `storyboard.json` is the contract between Planner and Coder — you can re-render the same
  storyboard with the other engine.

## Scope (v1)

- Mixed-engine single video is allowed but discouraged; record it as a known limitation.
- AI text-to-video (Sora/Veo) and avatar tools (HeyGen/Synthesia) are **out of scope** — they
  hurt educational rigor. They're noted in references as optional B-roll/presenter add-ons only.

## Reference index

- `references/engine-selection.md` — Manim vs Remotion vs motion heuristics + scoring.
- `references/motion-engine.md` — motion engine: project layout, time source (seconds, marks, cues), API, commands.
- `references/motion-rules.md` — render contract, springs, look and rhythm rules for motion lessons.
- `references/storyboard-schema.md` — `storyboard.json` schema + examples.
- `references/manim-patterns.md` — Manim API snippets + error→fix table (RITL-DOC corpus).
- `references/remotion-patterns.md` — Remotion API snippets + error→fix table (RITL-DOC corpus).
- `references/component-library.md` — reusable templates for both engines.
- `references/formats.md` — 16x9 / 1x1 / 4x5 / 9x16, safe areas, re-blocking, per-engine helpers.
- `references/presets.md` — looks (chalkboard, paper, blueprint, blank): file format and how engines use it.
- `references/verify-loop.md` — RITL + vision-critic rubric, frame sampling, retry caps, scored critic rounds.
- `references/critique.md` — prompt for the fresh critic: 8 criteria, caps, failure modes, log format.
- `references/tts-setup.md` — provider detection, recipes, word timings.
- `references/audio.md` — narration grid, cues, music bed, sfx, mix, mux.
- `references/troubleshooting.md` — Python 3.14/Manim, LaTeX, cairo/pango, ffmpeg, Chrome shell.
