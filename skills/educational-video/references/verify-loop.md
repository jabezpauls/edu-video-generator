# Verify loop: RITL, per-scene vision check, scored lesson critic

Three layers, cheapest first. Sections 1-5 run per scene while building (Code2Video Critic +
Renderer-in-the-Loop). Section 6 runs on the finished, muxed renders and decides when to ship.

## 1. RITL — deterministic error loop

```
render scene
if exit code == 0: go to vision critic
else:
  read .videogen/logs/scene_<id>.render.log
  classify error (Python traceback | TS/compile | LaTeX | Chrome | timeout)
  retrieve the failing-symbol entry from manim-patterns.md / remotion-patterns.md error→fix table
  apply a MINIMAL patch to the scene code
  re-render
  repeat — max 5 attempts
on exhaustion: HARD FAIL — stop the pipeline, show the user the log + last diff
```
Always patch the smallest region; don't rewrite the whole scene. Record `render_retries` per
scene in the manifest.

## 2. Frame extraction

Sample points = scene start, each animation-beat boundary (from `storyboard.beats[].t`), and
scene end. **Cap at 6 frames/scene** to bound tokens.

- Manim: `scripts/extract_frames.sh manim <project> <id> <t1,t2,...>` → ffmpeg seeks timestamps.
- Remotion: `scripts/extract_frames.sh remotion <project> <SceneId> <frame1,frame2,...>` →
  `remotion still` renders exact frames (cheaper than a full video).

Frames land in `.videogen/frames/scene_<id>_<t>.png`.

## 3. Vision critic

Read() each extracted PNG as an image and evaluate against this fixed rubric:

| Check | Fail condition |
|---|---|
| **Overlap** | text/objects collide or occlude each other |
| **Off-screen / safe-area** | anything clipped by frame edges or inside the 5% margin |
| **Legibility** | font too small at 1080p, low contrast, raw `$...$`/un-rendered LaTeX, overflowing lines |
| **Composition** | crowded in one corner, unbalanced, inconsistent with storyboard intent |
| **Beat-timing** | the element a beat says should be visible by time `t` is absent in that frame |

Return structured JSON to yourself:
```json
{ "verdict": "FIX",
  "issues": [
    {"type":"overlap","scene":"01","frame":2.5,"fix_hint":"shrink title to 0.7x and shift group DOWN 0.5"},
    {"type":"legibility","scene":"01","frame":6.0,"fix_hint":"equation rendered as raw text — use MathTex not Text"}
  ] }
```
Save to `.videogen/critic/scene_<id>_iter<N>.json`.

## 4. Fix routing

If `verdict == FIX`: switch to Coder hat, apply the `fix_hint`s as targeted edits, re-render
(back through RITL), re-extract, re-critique. **Max 3 critic-fix passes per scene.**

- PASS (per scene) = render exit 0 **AND** critic verdict PASS.
- Critic exhaustion is a **soft fail**: keep the best version, record outstanding issues in the
  manifest `warnings[]`, continue the pipeline (always produce output), surface at delivery.

## 5. Global guardrails

- Cumulative re-renders per run capped at **40**. If hit, deliver best-effort + report.
- Per-scene frame budget: **≤6**.
- If a fix would require changing the storyboard (not just code), note it and ask the user
  rather than silently diverging from the approved plan.

## 6. Scored lesson critic (final renders, any engine)

Run after the lesson is muxed (`output/final*.mp4`, or `renders/<fmt>.mp4` for the motion
engine). It judges only the rendered MP4s, so it is the same for Manim, Remotion and motion.

Modes (record in `manifest.json` as `critic_mode`):

| Mode | Rounds | Ships when |
|---|---|---|
| strict (default) | at least 3 | every score >= 8, and round >= 3 |
| `--quick` | 1 | every score >= 7 |

Each round:
1. `<project>/.venv/bin/python scripts/review.py <N> --project <project>` (or
   `uv run --with numpy --with pillow python scripts/review.py ...` when there is no venv) builds `review/r<N>/`: contact sheets,
   fast-action strips, phone sheets at 360 px per format, `safe_9x16.jpg`, `metrics.json`.
   Renders are discovered in `renders/` and `output/`; pass `--video <fmt>=<file>` otherwise.
   `cues.json` / `grid.json`, when present, add cue-to-picture sync; without them that metric is
   skipped and the critic judges sync by eye. Use `--mode short` for shorts (tighter thresholds).
2. Spawn a FRESH critic subagent (one that did not write the lesson, and a new one each
   round) with `references/critique.md`, the project path and the round number. It looks at every
   image, reads `metrics.json`, scores the 8 criteria and appends the round to
   `docs/review_log.md` in the exact format given there.
3. Update the manifest: `critic_rounds` += 1, `scores` = the latest round's scores, `critic_mode`.
4. Verdict SHIP per the table above, else fix the critic's 3 worst problems (smallest edits;
   re-run RITL for any scene touched), re-render, and go to the next round.
5. A critic that cannot be spawned: do the round yourself using the same file, keep its voice and
   do not defend the code.

Rules that keep the loop honest:
- Scores come from the critic, never from the Coder. Do not argue a score up; fix the picture.
- A problem still visible from the previous round cannot score higher than last round.
- A fix that needs a storyboard change goes to the user first.
- Cap strict mode at 6 rounds. If every score is still not >= 8, deliver the best round, list
  what is outstanding in `warnings[]`, and say so in the delivery message.
- Rounds count against the 40 re-render budget.

## Why this works

Deterministic tool-based critique (the compiler/renderer) catches every runtime error for free;
the vision critic catches the perceptual problems (overlap, clipping, illegible text) that a
compiler can't see. Doc-grounded retries (RITL-DOC) are what push render success toward ~94%.
