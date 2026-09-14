# Component library

Reusable scene templates with parallel Manim + Remotion implementations, and the motion-engine equivalents below. Instantiating these
from `storyboard.scenes[].template` (instead of writing raw animation) is what keeps output
consistent and minimizes critic-fix iterations. Each template encodes: safe-area margins,
default font sizes, palette colors, and sensible enter/exit timing.

Palette defaults: `bg #0e1116`, `fg #e6edf3`, `accent #58a6ff`, `accent2 #f78166`. When the
storyboard names a `preset`, take colours and fonts from it instead (`theme.BG / INK / ACCENT /
HIGHLIGHT` in Manim, `var(--bg)` / `var(--ink)` / `var(--accent)` / `var(--highlight)` in Remotion;
see `presets.md`) and size and place everything per format (see `formats.md`). An explicit
`storyboard.palette` overrides both. The hard-coded hex values below are the no-preset defaults.

## Template catalog

| Template | Use for | Key elements |
|---|---|---|
| `TitleCard` | section/title intro | big title + optional subtitle, centered |
| `BulletList` | enumerated points | staggered bullet build, left-aligned |
| `EquationReveal` | math derivation | `MathTex`/KaTeX written then highlighted |
| `CodeBlock` | show code | syntax-highlighted, optional line highlight |
| `DataChart` | data viz | bar/line chart from `data` |
| `LowerThird` | label/speaker tag | small banner bottom-left |
| `SceneTransition` | between scenes | fade/slide wipe |

## Manim implementations

```python
from manim import *

PALETTE = {"bg":"#0e1116","fg":"#e6edf3","accent":"#58a6ff","accent2":"#f78166"}

def title_card(scene, title, subtitle=None):
    scene.camera.background_color = PALETTE["bg"]
    t = Text(title, font_size=72, color=PALETTE["fg"])
    grp = VGroup(t)
    if subtitle:
        s = Text(subtitle, font_size=36, color=PALETTE["accent"])
        grp.add(s); grp.arrange(DOWN, buff=0.5)
    grp.scale_to_fit_width(min(grp.width, config.frame_width*0.9)).move_to(ORIGIN)
    scene.play(FadeIn(grp, shift=UP*0.3)); scene.wait(1)
    return grp

def bullet_list(scene, items):
    rows = VGroup(*[Text(f"• {x}", font_size=40, color=PALETTE["fg"]) for x in items])
    rows.arrange(DOWN, aligned_edge=LEFT, buff=0.4).to_edge(LEFT, buff=1.0)
    for r in rows:
        scene.play(FadeIn(r, shift=RIGHT*0.3), run_time=0.5)
    return rows

def equation_reveal(scene, tex):
    eq = MathTex(tex, color=PALETTE["fg"]).scale(1.4).move_to(ORIGIN)
    scene.play(Write(eq)); scene.wait(0.5)
    scene.play(Indicate(eq, color=PALETTE["accent"]))
    return eq
```
(For `CodeBlock` use `Code(code=..., language=...)`; `DataChart` use `BarChart(values, ...)`;
`LowerThird` a small `VGroup(Rectangle()+Text()).to_corner(DL)`.)

## Remotion implementations

```tsx
import { AbsoluteFill, interpolate, useCurrentFrame, Sequence } from "remotion";
const P = { bg:"#0e1116", fg:"#e6edf3", accent:"#58a6ff" };

export const TitleCard: React.FC<{title:string; subtitle?:string}> = ({title, subtitle}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0,20], [0,1], {extrapolateRight:"clamp"});
  return (
    <AbsoluteFill style={{background:P.bg, justifyContent:"center", alignItems:"center", padding:"6%", opacity:o}}>
      <h1 style={{color:P.fg, fontSize:84, margin:0, textAlign:"center"}}>{title}</h1>
      {subtitle && <h2 style={{color:P.accent, fontSize:40}}>{subtitle}</h2>}
    </AbsoluteFill>
  );
};

export const BulletList: React.FC<{items:string[]}> = ({items}) => (
  <AbsoluteFill style={{background:P.bg, padding:"8%", justifyContent:"center"}}>
    {items.map((it,i)=>(
      <Sequence key={i} from={i*15}>
        <Bullet text={it}/>
      </Sequence>
    ))}
  </AbsoluteFill>
);
const Bullet: React.FC<{text:string}> = ({text}) => {
  const f=useCurrentFrame();
  const x=interpolate(f,[0,12],[-30,0],{extrapolateRight:"clamp"});
  const o=interpolate(f,[0,12],[0,1],{extrapolateRight:"clamp"});
  return <div style={{color:P.fg,fontSize:44,opacity:o,transform:`translateX(${x}px)`,marginBottom:18}}>• {text}</div>;
};
```
(For `CodeBlock` use `@remotion/shiki`; `DataChart` use Recharts; `EquationReveal` render KaTeX.)

## Authoring rules

- Always center or pad to a ≥5% safe-area margin (`place` / `fmt.safe_bounds()` in Manim, `f.safe`
  in Remotion; 9:16 needs more); never hard-code coordinates that can overflow.
- Re-block for tall formats: side-by-side templates become stacked (`split`, `f.pick("row","column")`).
- Entrances use the shared springs (`springs.py` / `springs.ts`), not ad-hoc easing.
- Scale text groups to ≤90% of frame width.
- Use palette colors only, so all scenes look like one video.
- Keep one main idea per template instance; compose multiple via the storyboard, not one mega-scene.

## Motion engine

For `engine: motion` the templates are the lesson components in `film/edu/` plus the type helpers (`TYPE.line`,
`TYPE.rise`, `TYPE.type`). The full API is in `motion-components.md`; this section maps the storyboard onto it.

### Element kind to component

| `element.kind` | Motion component | Storyboard fields used |
|---|---|---|
| `equation` | `EDU.equation` | `tex` is the step's TeX; wrap the pieces the beats refer to in `\term{id}{...}`; several equations in a scene are steps |
| `code` | `EDU.code` | `value` is `code`, `lang` is `lang`; `highlight` beats become `focus` stops |
| `chart` (`line`, `bar`) | `EDU.plot` | `data` becomes `curves[].data` (line) or `bars` + `xCats` (bar) |
| `axes` | `EDU.plot` | functions become `curves[].fn`; marked points become `points` / `markers` |
| `shape` | `EDU.diagram` | `shape` and `label` become a node; arrows between shapes are `edges`; arrays and trees use `.array` / `.tree` |
| `text` | `TYPE.line` + `TYPE.rise` | `value`; one line per beat, swapped sequentially |
| `image` | a registered `<img>` (below) | `src` from `assets` |
| narration | `EDU.captions` | word timings from the grid (burned in for 9:16 and shorts) |

`element.position` becomes a box with `EDU.zone(position)` -> `{ x, y, w, h }`, per format: it keeps the margins, the 9:16
platform zones and the caption strip, and stacks `left` / `right` into upper / lower halves in tall frames.

Beats map to marks: `{ "t": 3, "action": "highlight", "target": "equation" }` is a mark (`"s02.start+3"`, or the `on` cue)
passed as the `at`, `from` or `reveal` of the component. Actions: `write`/`draw` are the component's own reveal
(equation terms, code typing, plot draws), `highlight` is `hi` / `focus` / a `hi` tone, `move` is `moves` or pointer
stops, `transform` is an equation step, `pop_in`/`slide_in` are the component's entrance, `fade_*` is not used for primary
elements (see `motion-rules.md`).

### Template to code

| Template | Motion |
|---|---|
| `TitleCard` | `TYPE.line` (display, accent word) + a quieter `TYPE.line` subtitle, both `rise`; hook on frame 0 |
| `BulletList` | one `TYPE.line` per bullet, `rise` on its own cue; earlier bullets dim to ~0.3, never vanish |
| `EquationReveal` | `EDU.equation` with `reveal` per term and a `hi` window on the term being discussed |
| `CodeBlock` | `EDU.code` with `reveal.mode: 'type'` and `focus` stops |
| `DataChart` | `EDU.plot` (`bars` or `curves[].data`) |
| `Diagram` | `EDU.diagram` / `.array` / `.tree` |
| `LowerThird` | a `TYPE.line` in the bottom-left of `EDU.zone('bottom-left')`, `rise` in and out |
| `SceneTransition` | a hard cut at the scene boundary (`C.scene` windows); a wipe via `pre`/`post` and `C.inset` only when it means something |

```js
// EquationReveal in a scene (the starter lesson shows all of them at work)
scene({ name: 's03', from: 's03.start', to: 's04.start',
  build(root, S) {
    const z = EDU.zone('center');
    S.eq = EDU.equation(root, { x: z.x, y: z.y, w: z.w, size: C.pick(150, 120, 130),
      steps: [{ tex: '\\term{lhs}{e^{i\\pi}} \\term{eq}{=} \\term{rhs}{-1}', at: 's03.start+0.4', reveal: { rhs: 's03.minus_one' } }],
      hi: [{ term: 'rhs', from: 's03.minus_one', to: 's03.end-1' }] });
  },
  run(t, S) { S.eq.run(t); },
});

// an image (a registered element like any other)
S.img = el('img', { src: '../assets/diagram.png', style: `position:absolute;left:${z.x}px;top:${z.y}px;width:${z.w}px` }, root);
reg(S.img, { o: 0 });   // run(t): const p = spHit(t, 's03.start+1', 'default'); put(S.img, { o: p > 0.001 ? 1 : 0, y: (1 - p) * 40, s: 0.94 + 0.06 * p });
```

Authoring rules for lessons, on top of the ones above: one idea per scene; reveal a term, a line or a node when the
narration reaches it; keep burned captions clear of content (`EDU.zone` reserves their strip); size text for the phone
sheet, not for the 16:9 frame; use the exact strings, numbers and code from the storyboard.
