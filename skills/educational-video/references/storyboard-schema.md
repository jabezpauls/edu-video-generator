# Storyboard schema

`storyboard.json` is the engine-agnostic contract between Planner and Coder. The same storyboard
can drive any engine. Validate with `scripts/validate_storyboard.py` before coding.

This is **schema v2**. Every v2 addition (`mode`, `formats`, `preset`, beat `on`, engine `motion`)
is optional, so storyboards written against the original schema keep validating unchanged.

## Schema

```jsonc
{
  "title": "string",                  // video title
  "audience": "string",               // e.g. "high-school", "undergrad", "general"
  "mode": "lesson",                   // "lesson" (default) | "short"
  "formats": ["16x9", "9x16"],        // output formats; default ["16x9"] (["9x16"] for a short)
  "preset": "chalkboard",             // look & feel preset slug; omit for the default look
  "aspect_ratio": "16:9",             // legacy: primary format, kept for v1 storyboards
  "resolution": "1920x1080",
  "fps": 30,
  "engine": "manim",                  // "manim" | "remotion" | "motion"
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
        { "on": "rotates", "action": "highlight", "target": "equation" }
      ],
      "est_duration_s": 12,
      "assets": []                    // files this scene needs under assets/
    }
  ]
}
```

## Field semantics

- **mode**: `lesson` (default) or `short`. A short is a 30-60 s micro-lesson (hook, one idea,
  payoff); the validator enforces `target_duration_s` in that range and the default format
  becomes `9x16`.
- **formats**: which outputs to produce. `16x9` (1920x1080), `1x1` (1080x1080), `4x5` (1080x1350),
  `9x16` (1080x1920). Non-empty, no duplicates. The first entry is the primary format; the
  legacy `aspect_ratio`/`resolution` fields only matter when `formats` is absent.
- **preset**: lowercase slug (`[a-z0-9_-]`) naming a look preset (palette, fonts, voice, music).
  Omit it to use the default look. An explicit `palette` overrides the preset's colours. Shipped:
  `chalkboard`, `paper`, `blueprint` (and `blank` for building your own); see `presets.md`.
- **engine**: `manim`, `remotion` or `motion`; `null` is allowed until engine selection has run.
- **palette**: optional object of colour name to hex string (`#rgb`, `#rrggbb`, `#rrggbbaa`).

- **scenes[].beats** drive two things: the Coder's animation sequence and the Critic's *timing
  expectations* (a beat at t=6 means that element must be visible by ~6s). Keep beats ordered.
- **beat timing: `t` and/or `on`.** A beat needs at least one. `t` is seconds from scene start.
  `on` anchors the beat to the narration instead: a word or cue spoken in that scene, so the
  visual lands as the word is said. If both are given, `t` is the estimate used until word
  timings exist and `on` wins afterwards. `t` values must still ascend among the beats that
  have one; `on` beats are ordered by the narration itself.
- **element.position** vocabulary: `center, top, bottom, left, right, top-left, top-right,
  bottom-left, bottom-right`. Templates map these to safe-area-respecting coordinates.
- **element.kind**: `equation` (LaTeX), `text`, `shape`, `image`, `code`, `chart`, `axes`.
- **action** vocabulary (engine-mapped): `fade_in, fade_out, write, draw, transform, highlight,
  move, scale, indicate, slide_in, pop_in`.
- **template**: name from `component-library.md`, or `"custom"` for hand-written scenes.

### Anchor syntax (`on`)

| Anchor | Meaning |
|---|---|
| `derivative` | first occurrence of that word in the scene's narration (lowercase, punctuation stripped) |
| `derivative#2` | the second occurrence (`#3`, ...) |
| `w12` | word at index 12 (zero-based) |
| `p2` | start of sentence/phrase 2 (one-based) |
| `start`, `end` | scene start / end of speech |
| `s03.derivative` | any of the above, qualified with a scene number (`s03` names scene `"03"`) |

Words may contain letters, digits, `'` and `-`. A qualified cue must name a scene that exists
(error) and should normally be the beat's own scene (warning otherwise).

## Rules

- Scene `id`s are unique and define order. Sum of `est_duration_s` must be within ±15% of
  `target_duration_s`.
- Every `assets[]` path must exist before Phase 5 (the Planner is responsible for sourcing or
  generating them; otherwise drop the element).
- A short (`mode: "short"`) must have `target_duration_s` between 30 and 60.
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
