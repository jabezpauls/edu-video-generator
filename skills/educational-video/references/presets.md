# Presets

A preset is a look: palette, two fonts, and the sound and caption defaults that go with them.
Name one in the storyboard (`"preset": "chalkboard"`) and every scene in every engine uses the
same colours and fonts, so scenes read as one video.

| preset | feel | palette | fonts |
|---|---|---|---|
| `chalkboard` | friendly, hand-lettered | slate green board, chalk ink, yellow accent, pink highlight | Caveat (display), Nunito (body) |
| `paper` | calm, bookish | warm off-white, dark ink, terracotta accent, blue highlight | Newsreader, Inter |
| `blueprint` | technical, precise | navy, pale blue ink, cyan accent, amber highlight | Space Grotesk, IBM Plex Mono |
| `blank` | none (every field documented) | engine defaults | system fonts |

All shipped fonts are SIL Open Font License; the licence text sits next to the font files
(`presets/<name>/fonts/OFL-*.txt`) and must stay with them.

## Colour roles

| token | role |
|---|---|
| `bg` | canvas |
| `ink` | titles, equations, primary text |
| `ink2` | body text, axes, labels |
| `accent` | the one object the lesson is about |
| `highlight` | the term being explained right now (use sparingly) |
| `card` | panels, code blocks, chart backgrounds |

One accent and one highlight: if everything is coloured, nothing is emphasised.

## The file

`presets/<name>/preset.jsonc` is JSON with comments and trailing commas. `presets/blank/preset.jsonc`
documents every field; copy that folder to make your own, either into the skill's `presets/` or
into `<project>/presets/` (a project preset wins over a shipped one with the same name). Empty
fields mean "use the default". Fields: `name`, `description`, `colors`, `fonts.display` /
`fonts.body` (`file` .woff2, `ttf` .ttf, `family`, `weight`, `tracking`), `voice` (per provider
plus a delivery note), `music`, `sfx`, `captions`, `cards`, `safe_area`, `notes`.

Fonts: only ship fonts you may redistribute. A font needs both files: `.woff2` for Remotion and
the motion engine, `.ttf` for Manim (Pango cannot read woff2). `family` must be the name inside
the `.ttf` (check with `fc-scan file.ttf`), and one file is one weight: ship a separate file per
weight rather than a variable font.

## Applying a preset

```bash
python3 scripts/apply_preset.py <preset> <project-dir>
```

(`scaffold_engine.sh` does this for you from the storyboard's `preset`, or with the blank
defaults when there is none.) It validates the preset and writes, inside the project:

| file | consumed by |
|---|---|
| `preset.json` | the resolved preset (defaults filled) for tools, the critic and the motion engine |
| `assets/fonts/{display,body}.{woff2,ttf}` | all engines |
| `scenes/theme.py` | Manim scenes |
| `scenes/src/theme.ts` | Remotion scenes |
| `scenes/public/fonts/*.woff2` | Remotion (`staticFile`) |

It also sets `preset` in `manifest.json`. Re-running with another preset just rewrites these.

### Manim

```python
import theme
from formats import place

class Scene01(Scene):
    def construct(self):
        theme.setup(self)                 # background, fonts, frame for EDU_FORMAT
        title = theme.title("Euler's identity")   # Text in the display font, INK
        note = theme.body("one line of context")  # Text in the body font, INK2
        eq = theme.eq(r"e^{i\pi}+1=0")            # MathTex in INK
        box = SurroundingRectangle(eq, color=theme.ACCENT)
```

Use `theme.BG / INK / INK2 / ACCENT / HIGHLIGHT / CARD` instead of literal colours.
`theme.FONT_DISPLAY` and `theme.FONT_BODY` are the Pango family names for `Text(font=...)`.
`MathTex` keeps LaTeX's own math fonts (a preset cannot sensibly swap them), only coloured.

### Remotion

```tsx
import { themeVars, COLORS, SAFE_AREA } from "./theme";

<AbsoluteFill style={{ ...themeVars, background: "var(--bg)", fontFamily: "var(--font-body)" }}>
  <h1 style={{ fontFamily: "var(--font-display)", color: "var(--ink)" }}>Title</h1>
```

`themeVars` defines `--bg --ink --ink-2 --accent --highlight --card --font-display --font-body`.
`COLORS` gives the same values for SVG attributes. Importing `theme.ts` loads the fonts and
holds the render until they are ready, so no frame is drawn in a fallback face.

### Motion engine

The motion engine reads `preset.jsonc` (or the resolved `preset.json`) directly: `colors`
become its `:root` tokens, `fonts.display` / `fonts.body` its two faces. Same field names, same
ids.

## What a preset does not change

Layout, spring presets and pacing are the same in every look. A preset changes how it looks, not
how it moves.
