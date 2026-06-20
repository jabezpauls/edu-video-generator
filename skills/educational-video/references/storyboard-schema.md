# Storyboard schema

`storyboard.json` is the engine-agnostic contract between Planner and Coder. The same storyboard
can drive either engine. Validate with `scripts/validate_storyboard.py` before coding.

## Schema

```jsonc
{
  "title": "string",                  // video title
  "audience": "string",               // e.g. "high-school", "undergrad", "general"
  "aspect_ratio": "16:9",             // "16:9" | "9:16" | "1:1"
  "resolution": "1920x1080",
  "fps": 30,
  "engine": "manim",                  // "manim" | "remotion" (from Phase 2)
  "engine_reason": "string",
  "language": "en",
  "narration": true,                  // whether to synthesize voiceover
  "target_duration_s": 180,
  "palette": {                        // optional; defaults applied if omitted
    "bg": "#0e1116", "fg": "#e6edf3", "accent": "#58a6ff", "accent2": "#f78166"
  },
  "scenes": [
    {
      "id": "01",                     // zero-padded, unique, ordered
      "title": "string",
      "narration": "Full sentence(s) spoken during this scene.",
      "template": "EquationReveal",   // a component-library template, or "custom"
      "elements": [
        { "kind": "equation", "tex": "e^{i\\theta}=\\cos\\theta+i\\sin\\theta", "position": "center" },
        { "kind": "text", "value": "The unit circle", "position": "top" },
        { "kind": "shape", "shape": "circle", "label": "unit circle", "position": "center" },
        { "kind": "image", "src": "assets/diagram.png", "position": "right" },
        { "kind": "code", "lang": "python", "value": "def f(x): return x*x", "position": "left" },
        { "kind": "chart", "chart_type": "bar", "data": [["A",3],["B",5]], "position": "center" }
      ],
      "beats": [
        { "t": 0.0, "action": "fade_in", "target": "unit circle" },
        { "t": 2.5, "action": "write",   "target": "equation" },
        { "t": 6.0, "action": "highlight", "target": "equation" }
      ],
      "est_duration_s": 12,
      "assets": []                    // files this scene needs under assets/
    }
  ]
}
```

## Field semantics

- **scenes[].beats** drive two things: the Coder's animation sequence and the Critic's *timing
  expectations* (a beat at t=6 means that element must be visible by ~6s). Keep beats ordered.
- **element.position** vocabulary: `center, top, bottom, left, right, top-left, top-right,
  bottom-left, bottom-right`. Templates map these to safe-area-respecting coordinates.
- **element.kind**: `equation` (LaTeX), `text`, `shape`, `image`, `code`, `chart`, `axes`.
- **action** vocabulary (engine-mapped): `fade_in, fade_out, write, draw, transform, highlight,
  move, scale, indicate, slide_in, pop_in`.
- **template**: name from `component-library.md`, or `"custom"` for hand-written scenes.

## Rules

- Scene `id`s are unique and define order. Sum of `est_duration_s` must be within ±15% of
  `target_duration_s`.
- Every `assets[]` path must exist before Phase 5 (the Planner is responsible for sourcing or
  generating them; otherwise drop the element).
- `narration` strings should be speakable (no raw LaTeX in narration — write "e to the i theta").

## Good vs bad

**Good scene** — one clear idea, ordered beats, speakable narration:
```json
{ "id":"02","title":"Rotation","narration":"Multiplying by i rotates the point ninety degrees.",
  "template":"EquationReveal",
  "elements":[{"kind":"equation","tex":"i\\cdot(a+bi)=-b+ai","position":"center"}],
  "beats":[{"t":0,"action":"write","target":"equation"},{"t":3,"action":"indicate","target":"equation"}],
  "est_duration_s":7,"assets":[] }
```

**Bad scene** — too many ideas, no beats, LaTeX in narration:
```json
{ "id":"02","narration":"$e^{i\\pi}=-1$ and also derivatives and integrals and limits",
  "elements":[ /* 9 unrelated elements */ ], "beats":[], "est_duration_s":2 }
```
