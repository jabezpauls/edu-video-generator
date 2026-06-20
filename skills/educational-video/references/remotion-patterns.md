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
| Audio | `<Audio src={staticFile("...")} />` |

## Map storyboard beats

A beat at `t` seconds → drive opacity/position from `frame` relative to `t*fps`, or wrap the
element in `<Sequence from={Math.round(t*fps)}>`. Actions: `fade_in→interpolate opacity 0→1`,
`slide_in→interpolate translateX`, `pop_in→spring scale`, `write→stagger children opacity`,
`highlight→interpolate a glow/scale pulse`.

## Duration

A scene's length = its `<Composition durationInFrames>`. To match narration, set
`durationInFrames = round(est_duration_s * fps)`; Phase-9 reconciliation bumps this if audio is
longer.

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
