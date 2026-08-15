// Read narration-grid cues from a Remotion scene (copy to <project>/scenes/src/gridsync.ts).
//
//   const g = useGrid("01");
//   const dot = interpolate(g.since("rotates"), [0, 0.5], [0, Math.PI / 2], clamp);
//
// Anchors are the storyboard `on` values: "rotates", "rotates#2", "w12", "p2", "end", or a
// qualified "s02.start". Times come from grid.json (scripts/grid.py), so the picture lands on
// the word exactly as the narration and the sound effects do. Audio is NOT added in Remotion:
// scripts/mux.sh muxes audio/mix.wav over the rendered scenes.
import { useCurrentFrame, useVideoConfig } from "remotion";
// scenes/src -> project root. Remotion's bundler resolves JSON imports.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const grid: GridData = require("../../grid.json");

export const HIT_LEAD = 0.06; // start visuals this long before the word so they read on it

export interface GridScene { id: string; n: number; start: number; end: number; duration: number }
export interface GridData { fps: number; duration: number; scenes: GridScene[]; cues: Record<string, number> }

export const gridData = grid;
export const sceneOf = (id: string): GridScene => {
  const s = grid.scenes.find((x) => x.id === id);
  if (!s) throw new Error(`scene ${id} is not in grid.json`);
  return s;
};

/** Composition length for a scene: its grid duration in frames. */
export const sceneFrames = (id: string, fps = grid.fps) => Math.round(sceneOf(id).duration * fps);

/** Seconds from the start of scene `id` to the anchor (negative if the anchor is in an earlier scene). */
export const cueIn = (id: string, anchor: string): number => {
  const sc = sceneOf(id);
  let name = anchor.toLowerCase();
  let prefix = `s${String(sc.n).padStart(2, "0")}`;
  const q = name.match(/^s(\d+)\.(.+)$/);
  if (q) { prefix = `s${q[1].padStart(2, "0")}`; name = q[2]; }
  const [base, nth] = name.split("#");
  const reserved = base === "start" || base === "end" || /^[wp]\d+$/.test(base);
  const key = nth && (nth !== "1" || reserved) ? `${prefix}.${base}#${nth}` : `${prefix}.${base}`;
  if (!(key in grid.cues)) throw new Error(`no cue "${anchor}" (looked for ${key}) in scene ${id}`);
  return grid.cues[key] - sc.start;
};

export const useGrid = (id: string) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps; // seconds since the scene started
  return {
    t,
    /** scene-local time of an anchor, in seconds */
    at: (anchor: string) => cueIn(id, anchor),
    /** seconds since the anchor, shifted so visuals lead by `lead`; negative before it */
    since: (anchor: string, lead = HIT_LEAD) => t - (cueIn(id, anchor) - lead),
    /** has the anchored word been spoken yet (with the visual lead)? */
    passed: (anchor: string, lead = HIT_LEAD) => t >= cueIn(id, anchor) - lead,
  };
};
