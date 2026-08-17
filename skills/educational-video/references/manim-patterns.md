# Manim patterns (Manim Community Edition, v0.19+)

Curated, version-correct snippets the Coder reads BEFORE writing, and the RITL loop retrieves on
render errors. Manim CE docs: https://docs.manim.community/

## Scene skeleton

```python
from manim import *

class Scene01(Scene):
    def construct(self):
        self.camera.background_color = "#0e1116"
        title = Text("The Unit Circle", color="#e6edf3").to_edge(UP)
        self.play(FadeIn(title))
        self.wait(1)
```

Render: `manim -qm scenes/scene_01.py Scene01` (medium). Final: `-qh`. Output lands under
`media/videos/scene_01/<quality>/Scene01.mp4` — `render.sh` copies it to `output/scene_01.mp4`.

## Core objects

| Need | Use |
|---|---|
| Plain text | `Text("...", font_size=48, color=...)` |
| LaTeX math | `MathTex(r"e^{i\pi}=-1")` |
| LaTeX paragraph | `Tex(r"...")` |
| Shapes | `Circle()`, `Square()`, `Rectangle()`, `Line()`, `Arrow()`, `Dot()` |
| Axes/plots | `Axes(x_range=[-3,3], y_range=[-2,2])`, `ax.plot(lambda x: x**2)` |
| Number plane | `NumberPlane()` |
| Groups | `VGroup(a, b, c).arrange(DOWN, buff=0.4)` |
| 3D | `class S(ThreeDScene)`, `self.set_camera_orientation(phi=70*DEGREES, theta=30*DEGREES)` |

## Animations

```python
self.play(Write(eq))                       # write text/LaTeX
self.play(Create(circle))                  # draw a shape
self.play(FadeIn(obj), FadeOut(other))     # fades, run concurrently
self.play(Transform(a, b))                 # morph a into b
self.play(Indicate(eq), run_time=0.8)      # emphasis flash
self.play(obj.animate.shift(RIGHT*2))      # .animate for property changes
self.play(obj.animate.scale(1.5).set_color(YELLOW))
self.wait(2)                               # hold
```

Map storyboard `action`s: `write→Write`, `draw→Create`, `fade_in→FadeIn`, `fade_out→FadeOut`,
`transform→Transform`, `highlight/indicate→Indicate`, `move→.animate.shift`, `scale→.animate.scale`,
`slide_in→FadeIn(shift=...)`, `pop_in→GrowFromCenter`.

## Positioning (respect safe area)

Frame is ~14.22 wide × 8 tall (units). Keep content within ~90%.
```python
obj.to_edge(UP, buff=0.6)          # near top, with margin
obj.to_corner(UL)                  # corner
obj.move_to(ORIGIN)                # center
obj.next_to(other, DOWN, buff=0.4) # relative
VGroup(a,b).arrange(DOWN, buff=0.5).move_to(ORIGIN)  # stack & center
```
Prevent overlap: build groups with `.arrange()` and `buff`; never hard-code overlapping coords.

## Timing to match narration (read the grid)

Scene length and beat times come from `grid.json` (see `audio.md`), never from guesses. Copy
`templates/gridsync.py` to `scenes/gridsync.py` and subclass `GridScene`:

```python
from manim import *
from gridsync import GridScene

class Scene01(GridScene):
    SCENE_ID = "01"                      # storyboard scene id

    def construct(self):
        title = Text("i times z").to_edge(UP)
        self.play(FadeIn(title), run_time=0.8)
        self.wait_until("rotates")       # hold until the word is said (starts 0.06 s early)
        self.play(FadeIn(dot, scale=0.4), run_time=0.4)
        self.wait_until("ninety")        # same anchors as the storyboard `on` values
        self.play(Create(arc), run_time=0.5)
        self.finish()                    # hold to the end of the scene's slot
```

- `wait_until(anchor)` waits until `anchor - 0.06 s` of the scene's own clock; it does nothing if
  the animation is already past it (so a slow `run_time` never makes things drift later, it just
  stops waiting). Anchors: `"rotates"`, `"rotates#2"`, `"w12"`, `"p2"`, `"end"`, `"s02.start"`.
- Keep every `run_time` short (0.3 to 1 s) so the next `wait_until` has room. If an animation
  would still be running when the next word is spoken, shorten it or use `lag_ratio`.
- `self.finish()` makes the render exactly as long as its grid slot; `mux.sh` conforms small
  differences and warns on big ones. Never end a scene with a fixed `self.wait(2)`.
- Use `self.grid.cue("p2")` for the raw seconds, e.g. to size a `run_time` that must end on the
  next phrase: `run_time=self.grid.cue("p2") - self.now - 0.06`.
- Do not attach audio in Manim (`add_sound`): `mux.sh` muxes the mastered mix over the scenes.
- `render.sh` quality `med` is 720p30 and `high` is 1080p60; `mux.sh` resamples every scene to the
  grid's fps, so the mix of qualities across iterations is harmless.
- Sound effects need no code: `grid.py cues` derives them from the same beats (`audio.md`).

## Error → fix table (RITL-DOC)

| Error / symptom | Cause | Fix |
|---|---|---|
| `LaTeX Error` / `dvisvgm` fails | bad TeX or missing package | Check the `MathTex`/`Tex` string; escape with raw string `r"..."`; for special pkgs add a `TexTemplate`. See troubleshooting. |
| `There is no module named 'manim'` | wrong interpreter | Run via the project venv: `.venv/bin/manim` (render.sh does this). |
| Text/objects overlap in frame | hard-coded coords | Use `VGroup(...).arrange()` + `next_to` + `buff`, then `move_to(ORIGIN)`. |
| Object clipped off-screen | placed beyond frame | Use `to_edge(..., buff=0.6)`; scale group with `.scale_to_fit_width(config.frame_width*0.9)`. |
| `MathTex` shows raw `$...$` text | used `Text` for math | Use `MathTex`/`Tex`, not `Text`. |
| `AttributeError: animate` chain fails | animating non-animatable | Wrap property change in `obj.animate.<prop>`; some need `Transform`. |
| Nothing renders / blank | forgot `self.play`/`self.add` | Add the mobject to the scene. |
| 3D looks flat | missing camera orientation | `self.set_camera_orientation(phi=..., theta=...)`. |
| Render very slow | high quality during iteration | Use `-qm` until final, `-qh` only for delivery. |
| Colors invisible on bg | low contrast | Set `self.camera.background_color` and pick fg from the palette. |
