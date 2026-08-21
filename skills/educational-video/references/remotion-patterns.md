# Remotion patterns (current Remotion 4.x)

Curated snippets the Coder reads before writing, and the RITL loop retrieves on errors.
Docs: https://www.remotion.dev/docs/

## Project shape

A bootstrapped Remotion project lives under the per-run `scenes/` workspace:
```
scenes/
  package.json
  remotion.config.ts
  src/
    index.ts        # registerRoot(Root)
    Root.tsx        # scene registry: one <SceneFormats> per scene
    Scene01.tsx ... # scene components
    springs.ts      # closed-form springs (same presets as Manim and the motion engine)
    formats.ts      # useFormat(): 16x9 / 1x1 / 4x5 / 9x16 layout and safe areas
    SceneFormats.tsx# registers a scene as one composition per format
    theme.ts        # generated from the storyboard's preset: colours, CSS vars, fonts
  public/fonts/     # the preset's .woff2 files
```

`scripts/scaffold_engine.sh` (run by bootstrap) copies the helpers and writes `theme.ts`.

`src/index.ts`:
```ts
import { registerRoot } from "remotion";
import { Root } from "./Root";
registerRoot(Root);
```

`src/Root.tsx` registers every scene as a composition:
```tsx
import { Scene01 } from "./Scene01";
import { SceneFormats } from "./SceneFormats";

export const Root = () => (
  <>
    <SceneFormats id="Scene01" component={Scene01} seconds={12} />   {/* 16x9, 1x1, 4x5, 9x16 */}
  </>
);
```

Composition ids: `Scene01` (16x9), `Scene01-1x1`, `Scene01-4x5`, `Scene01-9x16`. Render with
`render.sh remotion <project> 01 high 9x16`, or directly:
`npx remotion render src/index.ts Scene01-9x16 ../output/scene_01.9x16.mp4`.
Single frame for the critic: `npx remotion still src/index.ts Scene01 out.png --frame=75`.

## Scene component

```tsx
import { AbsoluteFill } from "remotion";
import { useFormat } from "./formats";
import { useSpring } from "./springs";
import { SAFE_AREA, themeVars } from "./theme";

export const Scene01: React.FC = () => {
  const f = useFormat(SAFE_AREA);
  const t = useSpring("heavy");                  // 0 -> 1, released at the scene start
  return (
    <AbsoluteFill style={{ ...themeVars, background: "var(--bg)", padding: f.safe.px,
                           justifyContent: "center", alignItems: "center" }}>
      <h1 style={{ fontFamily: "var(--font-display)", color: "var(--ink)", fontSize: f.pick(96, 88, 92),
                   margin: 0, opacity: Math.min(1, t * 2), transform: `translateY(${(1 - t) * 40}px)` }}>
        The Unit Circle
      </h1>
    </AbsoluteFill>
  );
};
```

## Springs (consistent motion)

Use `springs.ts`, not Remotion's physics `spring()`: the same four presets and the same maths as
Manim and the motion engine, so a lesson moves identically whichever engine draws it.

| preset | feel | for |
|---|---|---|
| `snappy` | fast, ~1.5 % overshoot | toggles, leading edges, small items |
| `default` | smooth, ~0.5 % overshoot | cards, containers, camera |
| `heavy` | no overshoot | big type, titles |
| `playful` | ~20 % overshoot | one-off emphasis only |

```tsx
const s = useSpring("snappy", 0.5);                    // hook: current frame, released at 0.5 s
const x = spring(t, 1.0, 0, 300, "default");           // t in seconds: from 0 to 300, released at 1.0 s
const y = track(t, [[0, 0], [1, 100], [2, -50]]);      // several targets, no restarts
const frames = Math.round(settle("heavy") * fps);      // how long it takes to settle
```

A spring is 0 before its release time and settles within `settle(preset)` seconds. Drive entrances
from `useSpring` rather than `interpolate` over a fixed frame range, and avoid pure-opacity
fades for primary elements: pair them with a spring move.

## Core APIs

| Need | Use |
|---|---|
| Current frame | `useCurrentFrame()` |
| fps / dims | `useVideoConfig()` |
| Tween a value | `interpolate(frame, [inFrame,outFrame], [from,to], {extrapolateLeft:"clamp", extrapolateRight:"clamp"})` |
| Spring/physics | `spring({frame, fps, config})` |
| Time-shift a child | `<Sequence from={fps*2} durationInFrames={fps*4}>...</Sequence>` |
| Full-bleed layer | `<AbsoluteFill>` |
| Math | KaTeX via `@remotion/google-fonts` + a KaTeX component, or render to SVG |
| Code highlighting | `@remotion/shiki` or prism; show as styled `<pre>` |
| Charts | Recharts/D3 inside the component |
| Audio | none in scenes: `mux.sh` adds the mastered mix (`audio.md`) |

## Map storyboard beats

A beat at `t` seconds → drive opacity/position from `frame` relative to `t*fps`, or wrap the
element in `<Sequence from={Math.round(t*fps)}>`. Actions: `fade_in→interpolate opacity 0→1`,
`slide_in→interpolate translateX`, `pop_in→spring scale`, `write→stagger children opacity`,
`highlight→interpolate a glow/scale pulse`.

## Duration and word sync (read the grid)

A scene's length is its grid slot, and its beats are the grid's word times (see `audio.md`).
Copy `templates/gridsync.ts` to `scenes/src/gridsync.ts`:

```tsx
import { AbsoluteFill, interpolate, Easing } from "remotion";
import { useGrid, sceneFrames, gridData } from "./gridsync";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) } as const;

export const Scene01: React.FC = () => {
  const g = useGrid("01");                                   // storyboard scene id
  const dot = interpolate(g.since("rotates"), [0, 0.4], [0, 1], clamp);   // 0 -> 1 as the word is said
  const arc = interpolate(g.since("ninety"), [0, 0.5], [0, 1], clamp);
  return <AbsoluteFill>{/* ... drive opacity / position from dot and arc ... */}</AbsoluteFill>;
};

// Root.tsx: the composition is exactly as long as its slot
<Composition id="Scene01" component={Scene01} durationInFrames={sceneFrames("01")}
             fps={gridData.fps} width={1920} height={1080} />
```

- `g.since(anchor)` is seconds since the anchored word, shifted 0.06 s early so the visual reads
  on the word; it is negative before that, so `interpolate` with clamping holds the start state.
  `g.passed(anchor)` is the boolean form, `g.at(anchor)` the scene-local time in seconds.
- Anchors match the storyboard `on` values: `"rotates"`, `"rotates#2"`, `"w12"`, `"p2"`, `"end"`,
  `"s02.start"`. A missing anchor throws, naming the cue it looked for.
- `grid.json` is imported from the project root (`../../grid.json` from `scenes/src`), so re-run
  `grid.py` and re-render after changing narration; the render is deterministic from the grid.
- Do not add `<Audio>`: `mux.sh` muxes the mastered mix over the scenes, which is what keeps
  loudness at -14 LUFS. Sound effects come from `grid.py cues`, not from code.
- Prefer `interpolate` and closed-form easing keyed on `g.since(...)` over `spring()` for
  anything that must land on a word: a physics spring's settle time varies with its config, a
  clamped interpolation reaches its end exactly when you say.

## Safe area & legibility

Wrap content in a padded container (≥5% margins). Use `fontSize` ≥ ~36px at 1080p. Keep
`backgroundColor` from the palette and ensure text contrast.

## Error → fix table (RITL-DOC)

| Error / symptom | Cause | Fix |
|---|---|---|
| `Composition with id "X" not found` | not registered | Add `<Composition id="X" .../>` in `Root.tsx`. |
| Cannot find module / TS error | bad import/path | Fix import; ensure file exported; run from `scenes/`. |
| Chrome download / launch fails | headless shell missing | `npx remotion browser ensure`; see troubleshooting. |
| Blank/black frame | animating before mount / opacity 0 | Check `interpolate` ranges; clamp extrapolation. |
| Element off-screen | absolute positioning overflow | Use fl/center via `AbsoluteFill` + flexbox; add padding. |
| Animation janky/instant | wrong frame math | Multiply seconds by `fps`; clamp `interpolate`. |
| Font not applied | font not loaded | Import `./theme` (it loads the preset's fonts and holds the render) and use `var(--font-display)`; with no preset, load via `@remotion/google-fonts`. |
| Layout wrong in 9:16 | scene written for 16:9 | Read `useFormat()` and use `f.pick(...)` / `f.safe`; render the `Scene01-9x16` composition. |
| `Composition with id "Scene01-9x16" not found` | scene registered with `<Composition>` only | Register with `<SceneFormats>`. |
| Render slow | high concurrency/quality | Render scenes individually; lower `--concurrency` if OOM. |
