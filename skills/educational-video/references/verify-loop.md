# Verify loop: RITL + vision critic

The core of the skill (Code2Video Critic + Renderer-in-the-Loop). Run per scene, in this order.

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

## Why this works

Deterministic tool-based critique (the compiler/renderer) catches every runtime error for free;
the vision critic catches the perceptual problems (overlap, clipping, illegible text) that a
compiler can't see. Doc-grounded retries (RITL-DOC) are what push render success toward ~94%.
