# Engine selection: Manim, Remotion or motion

All three engines are first-class. Pick **one per video** (mixing is allowed but discouraged).
Score the content on the three axes below, highest wins; on a tie use the STEM→Manim default.

## Scoring

Rate each axis 0.0–1.0, then compare.

**Math / geometric / numeric rigor (→ Manim):**
- Equations, derivations, LaTeX-heavy content
- Graphs, function plots, calculus, geometry, vectors, coordinate systems/planes
- Physics/chemistry diagrams, simulations, vector fields
- Algorithm animation that is really math: recurrences, geometric constructions, graphs of functions, precise morphing
- 3D scenes, parametric curves, number lines

**Web / text / design / UI (→ Remotion):**
- UI/product walkthroughs, web-app explainers, code editors w/ syntax highlighting
- Text-heavy slideshows, bullet builds, lower-thirds
- HTML/CSS layout, SVG logos, charts via JS libs (Recharts/D3), embedded images/screenshots
- Brand-consistent design systems, custom fonts, data-driven templated videos

**Concept / kinetic / stepping (→ motion):**
- Concept explainers where the idea is a sequence of states: "what is a hash table", "why does binary search halve the list"
- Algorithm and data-structure stepping: arrays, pointers, trees and graphs moving between states, one step per sentence
- Kinetic typography, definitions and key-term builds, recaps, "three things to remember"
- Shorts and social cuts (30–60 s, 9:16): the engine is built to re-block a lesson per format
- Anything that should *feel* designed and spring-driven, with sound later synced to the narration

Write the scores + the decision into `manifest.json`:
```json
{ "engine": "manim", "engine_reason": "math_rigor 0.9 > web_design 0.1 (equations + unit circle)" }
```

## Quick heuristics

| Signal in the topic/script | Lean |
|---|---|
| LaTeX, ∑/∫/∂, "prove", "graph of", "transform" | Manim |
| algorithm that is mostly math (recurrence, geometry, plots) | Manim |
| "walk through the app/UI", screenshots, code on screen | Remotion |
| brand colors, logo, marketing-style explainer | Remotion |
| slideshow, bullet points, talking-head + captions | Remotion |
| 3D, vector field, geometry construction | Manim |
| step through binary search / a stack / a sort, "explain the idea", recap, key-term build | motion |
| short / reel / 9:16 micro-lesson, kinetic type | motion |
| a derivation whose steps must be typeset LaTeX | Manim |

## Overrides

- The user's explicit choice always wins — record `engine_reason: "user override"`.
- `mode: "short"` defaults to **motion** (record `engine_reason: "short mode default"`), unless the user chose otherwise.
- A lesson that is mostly a derivation but has an algorithm section: Manim for the derivation, and tell the user the
  algorithm section could be a separate motion short; do not mix engines in one video.
- If the chosen engine fails to bootstrap (e.g. Manim install fails on this machine), fall back
  to the other and record the reason; do not silently proceed.

## Strengths / costs

- **Manim**: unmatched for math/geometry; LaTeX via the system `pdflatex`/`dvisvgm`; Python.
  Render is CPU-bound; medium quality (`-qm`) during iteration, high (`-qh`) for final.
- **Motion**: a pure `seek(t)` HTML page rendered frame by frame in headless Chromium (Playwright + ffmpeg). Closed-form
  springs, so the feel is consistent and any frame can be painted alone (contact sheets and critic frames take seconds,
  no video needed); per-format re-blocking for 16x9, 1x1, 4x5 and 9x16; a time source in seconds with named cues that
  narration will plug into. Cost: you author the film in JS (`film/film.js`) rather than a high-level scene API, and
  heavy LaTeX and geometry constructions are Manim's job. Set up with `bootstrap.sh <project> motion`; see `motion-engine.md`
  and `motion-rules.md`.
- **Remotion**: web-native (any HTML/CSS/SVG/JS asset), great typography & data viz; renders via
  headless Chrome; supports single-frame `remotion still` (cheap critic frames).
