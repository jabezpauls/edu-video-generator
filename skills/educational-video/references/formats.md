# Formats

One storyboard can be rendered into four shapes. The layout is **re-blocked per format**, never
cropped or squeezed: a side-by-side diagram on 16:9 becomes a stack on 9:16.

| id | size | use | layout family |
|---|---|---|---|
| `16x9` | 1920x1080 | YouTube, slides, desktop | wide |
| `1x1` | 1080x1080 | feed posts | square |
| `4x5` | 1080x1350 | Instagram / LinkedIn portrait | square (taller) |
| `9x16` | 1080x1920 | Shorts, Reels, TikTok | tall |

The storyboard's `formats` array selects what to produce; the first entry is the primary format.
`render.sh <engine> <project> <scene|all> <quality> [format|all]` renders one format, or every
format in the storyboard with `all`. Without the format argument it renders 16x9 into
`output/scene_<id>.mp4` exactly as before; with one, the file is `output/scene_<id>.<format>.mp4`
(`extract_frames.sh` takes the same format as an optional last argument).

## Pixel density is constant

Every format keeps the pixel size of text and strokes the same as 16x9, so a 48 px label is as
big on a phone as on a monitor. Only the canvas changes shape. In Manim that means the short side
is always 8 units (135 px per unit): 14.22 x 8, 8 x 8, 8 x 10, 8 x 14.22.

## Safe areas

Content stays inside the safe area; backgrounds may bleed.

| format | top | bottom | left | right |
|---|---|---|---|---|
| 16x9, 1x1, 4x5 | 5 % | 5 % | 5 % | 5 % |
| 9x16 | 14 % | 20 % | 5 % | 12 % |

The 9:16 numbers keep clear of the platform's title bar, caption/like stack and right-hand
buttons. A preset can change them (`safe_area`, see `presets.md`). The critic checks 9:16
frames against them.

## Re-blocking rules

- **Side by side becomes stacked.** Two blocks (plot + equation, code + output) go in a row on
  16x9 and a column on every other format. Put the one the narration mentions first on top.
- **Text size stays, line length shrinks.** On 9:16 the usable width is about 0.83 x 1080 px:
  break long equations over lines (`\\` / `aligned`) instead of shrinking them.
- **One focal object.** Tall formats have room for two stacked blocks, not four. If a 16x9 scene
  has three side-by-side panels, show them one after another on 9:16.
- **Titles move into the safe top, captions into the safe bottom.** Do not anchor anything at
  the frame edge.
- **Phone check.** If a label would be under ~32 px high on 1080 px width, it is too small.

## Manim: `scenes/formats.py`

Copied into the project by `scaffold_engine.sh` (bootstrap runs it). `render.sh` writes a
per-format config (`.videogen/manim_<fmt>_<quality>.cfg`) so the frame is correct before the
scene is imported, and sets `EDU_FORMAT`.

```python
from formats import fmt, split, stack, place, fit

fmt.id            # "16x9" | "1x1" | "4x5" | "9x16"   (from EDU_FORMAT)
fmt.pick(a, b, c) # wide, square, tall  (4x5 uses b)
fmt.safe_bounds() # (left, right, top, bottom) in scene units

place(title, "title")            # title | caption | center | left | right, inside the safe area
group = split(plot, equation)    # row on 16x9, column elsewhere; centred, scaled to fit
stack(a, b, c)                   # always a column
fit(mob, max_w=0.9)              # scale down (never up) to a fraction of the safe area
```

`fmt` reads the environment once at import. To check a layout without `render.sh`:
`python3 scenes/formats.py --config 9x16 med > f.cfg` and
`EDU_FORMAT=9x16 manim --config_file f.cfg scenes/scene_01.py Scene01`.

## Remotion: one composition per format

`SceneFormats` registers a scene as four compositions. Ids are `Scene01` for 16x9 and
`Scene01-1x1`, `Scene01-4x5`, `Scene01-9x16` for the rest.

```tsx
// src/Root.tsx
<SceneFormats id="Scene01" component={Scene01} seconds={12} />
```

Inside the scene, `useFormat()` says what is being drawn:

```tsx
const f = useFormat(SAFE_AREA);              // SAFE_AREA comes from the preset's theme.ts
<AbsoluteFill style={{ padding: f.safe.px }}>   // top right bottom left, in px
  <div style={{ flexDirection: f.pick("row", "column"), gap: f.pick(110, 60) }} />
```

`f.pick(wide, square, tall)`, `f.orientation`, `f.width/height`, `f.safe.{top,bottom,left,right,width,height}`.

## Subtitles per format

Soft subtitles (mov_text) for 16x9, 1x1 and 4x5; burned in for 9x16, where players do not
show a subtitle track. Burned captions respect the bottom safe area.

## Motion engine

`C.pick(wide, square, tall)` does the same job inside the motion engine. Presets and formats use
the same ids everywhere.
