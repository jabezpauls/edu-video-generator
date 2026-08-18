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
    Root.tsx        # <Composition> registry — one per scene
    Scene01.tsx ... # scene components
```

`src/index.ts`:
```ts
import { registerRoot } from "remotion";
import { Root } from "./Root";
registerRoot(Root);
```

`src/Root.tsx` registers every scene as a composition:
```tsx
import { Composition } from "remotion";
import { Scene01 } from "./Scene01";

export const Root = () => (
  <>
    <Composition id="Scene01" component={Scene01}
      durationInFrames={12 * 30} fps={30} width={1920} height={1080} />
  </>
);
```

Render: `npx remotion render src/index.ts Scene01 ../output/scene_01.mp4`.
Single frame for the critic: `npx remotion still src/index.ts Scene01 out.png --frame=75`.

## Scene component

```tsx
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Sequence } from "remotion";

export const Scene01: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const scale = spring({ frame, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill style={{ backgroundColor: "#0e1116", justifyContent: "center", alignItems: "center" }}>
      <h1 style={{ color: "#e6edf3", fontSize: 80, opacity, transform: `scale(${scale})` }}>
        The Unit Circle
      </h1>
    </AbsoluteFill>
  );
};
```

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
| Font not applied | font not loaded | Load via `@remotion/google-fonts` and set `fontFamily`. |
| Render slow | high concurrency/quality | Render scenes individually; lower `--concurrency` if OOM. |
