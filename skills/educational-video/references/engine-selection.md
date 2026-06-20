# Engine selection: Manim vs Remotion

Both engines are first-class. Pick **one per video** (mixing is allowed but discouraged in v1).
Score the content on two axes, higher score wins; on a tie use the STEM→Manim default.

## Scoring

Rate each axis 0.0–1.0, then compare.

**Math / geometric / numeric rigor (→ Manim):**
- Equations, derivations, LaTeX-heavy content
- Graphs, function plots, calculus, geometry, vectors, coordinate systems/planes
- Physics/chemistry diagrams, simulations, vector fields
- Algorithm or data-structure animation where precise morphing/positioning matters
- 3D scenes, parametric curves, number lines

**Web / text / design / UI (→ Remotion):**
- UI/product walkthroughs, web-app explainers, code editors w/ syntax highlighting
- Text-heavy slideshows, kinetic typography, bullet builds, lower-thirds
- HTML/CSS layout, SVG logos, charts via JS libs (Recharts/D3), embedded images/screenshots
- Brand-consistent design systems, custom fonts, data-driven templated videos

Write both scores + the decision into `manifest.json`:
```json
{ "engine": "manim", "engine_reason": "math_rigor 0.9 > web_design 0.1 (equations + unit circle)" }
```

## Quick heuristics

| Signal in the topic/script | Lean |
|---|---|
| LaTeX, ∑/∫/∂, "prove", "graph of", "transform" | Manim |
| "show the algorithm", tree/graph/array animation | Manim |
| "walk through the app/UI", screenshots, code on screen | Remotion |
| brand colors, logo, marketing-style explainer | Remotion |
| slideshow, bullet points, talking-head + captions | Remotion |
| 3D, vector field, geometry construction | Manim |

## Overrides

- The user's explicit choice always wins — record `engine_reason: "user override"`.
- If the chosen engine fails to bootstrap (e.g. Manim install fails on this machine), fall back
  to the other and record the reason; do not silently proceed.

## Strengths / costs

- **Manim**: unmatched for math/geometry; LaTeX via the system `pdflatex`/`dvisvgm`; Python.
  Render is CPU-bound; medium quality (`-qm`) during iteration, high (`-qh`) for final.
- **Remotion**: web-native (any HTML/CSS/SVG/JS asset), great typography & data viz; renders via
  headless Chrome; supports single-frame `remotion still` (cheap critic frames).
