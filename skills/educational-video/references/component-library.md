# Component library

Reusable scene templates with parallel Manim + Remotion implementations. Instantiating these
from `storyboard.scenes[].template` (instead of writing raw animation) is what keeps output
consistent and minimizes critic-fix iterations. Each template encodes: safe-area margins,
default font sizes, palette colors, and sensible enter/exit timing.

Palette defaults (override via `storyboard.palette`): `bg #0e1116`, `fg #e6edf3`,
`accent #58a6ff`, `accent2 #f78166`.

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

- Always center or pad to a ≥5% safe-area margin; never hard-code coordinates that can overflow.
- Scale text groups to ≤90% of frame width.
- Use palette colors only, so all scenes look like one video.
- Keep one main idea per template instance; compose multiple via the storyboard, not one mega-scene.
