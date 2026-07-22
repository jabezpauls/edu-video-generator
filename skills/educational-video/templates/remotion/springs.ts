// Closed-form springs for Remotion. Every function is a pure function of time, so any frame can
// be rendered in any order. These are NOT Remotion's physics `spring()`: they use the same four
// presets and the same maths as the Manim helper (springs.py) and the motion engine, so a lesson
// moves the same way whichever engine draws it.
//
// A spring is a damped harmonic oscillator released at rest toward a new target. Its unit step
// response goes 0 -> 1 and is 0 at and before the release.
//
//   import { useSpring, spr, SPRING } from "./springs";
//   const s = useSpring("snappy", 0.5);        // 0 -> 1, released 0.5 s into the scene
//   <div style={{ transform: `translateY(${(1 - s) * 40}px)` }} />
import { useCurrentFrame, useVideoConfig } from "remotion";

export type SpringName = "snappy" | "default" | "heavy" | "playful";
export type SpringParams = { response: number; damping: number };
export type SpringLike = SpringName | SpringParams;

// response: seconds for one undamped period; damping: ratio (zeta).
// Overshoot of a step = exp(-pi*z / sqrt(1 - z^2)) for z < 1.
export const SPRING: Record<SpringName, SpringParams> = {
  snappy: { response: 0.22, damping: 0.8 }, //   ~1.5% overshoot - toggles, leading edges
  default: { response: 0.4, damping: 0.86 }, //  ~0.5% overshoot - cards, containers, camera
  heavy: { response: 0.5, damping: 1.0 }, //     none (critical) - big type, titles
  playful: { response: 0.5, damping: 0.45 }, //  ~20% overshoot  - mascots, one-off emphasis
};

function resolve(p?: SpringLike | null): SpringParams {
  if (p == null) return SPRING.default;
  if (typeof p === "string") {
    const r = SPRING[p];
    if (!r) throw new Error(`springs: unknown preset "${p}"`);
    return r;
  }
  return p;
}

/** Unit step response of a spring released `tau` seconds ago. 0 for tau <= 0. */
export function step(tau: number, preset?: SpringLike): number {
  if (!(tau > 0)) return 0;
  const { response, damping: z } = resolve(preset);
  const w = (2 * Math.PI) / response;
  if (z < 1) {
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * tau) * (Math.cos(wd * tau) + ((z * w) / wd) * Math.sin(wd * tau));
  }
  if (z === 1) return 1 - Math.exp(-w * tau) * (1 + w * tau);
  const wd = w * Math.sqrt(z * z - 1); // overdamped
  return 1 - Math.exp(-z * w * tau) * (Math.cosh(wd * tau) + ((z * w) / wd) * Math.sinh(wd * tau));
}

const settleCache = new Map<string, number>();

/** Seconds until the response stays within `eps` of its target for good. */
export function settle(preset?: SpringLike, eps = 0.01): number {
  const p = resolve(preset);
  const key = `${p.response}/${p.damping}/${eps}`;
  const hit = settleCache.get(key);
  if (hit !== undefined) return hit;
  let last = 0;
  for (let tau = 0; tau < 20 * p.response; tau += 0.001) {
    if (Math.abs(1 - step(tau, p)) >= eps) last = tau;
  }
  settleCache.set(key, last);
  return last;
}

/** One spring from `from` to `to`, released at t0 (seconds). */
export function spring(t: number, t0: number, from: number, to: number, preset?: SpringLike): number {
  return from + (to - from) * step(t - t0, preset);
}

/**
 * A value with several targets: the sum of one spring per change, each released at its own time.
 * Springs are never restarted, so a new target mid-flight keeps the velocity of the ones still
 * settling.
 *
 * keys: [[t, value, preset?], ...] sorted by t. The first key is the initial value (its time is
 * ignored).
 */
export function track(
  t: number,
  keys: ReadonlyArray<readonly [number, number, SpringLike?]>,
  preset?: SpringLike,
): number {
  let v = keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [ti, vi, pi] = keys[i];
    if (t <= ti) break;
    v += (vi - keys[i - 1][1]) * step(t - ti, pi ?? preset);
  }
  return v;
}

/** Frame-based form of `step`: the response `frame` frames into a scene, released at `delaySec`. */
export function spr(frame: number, fps: number, preset?: SpringLike, delaySec = 0): number {
  return step(frame / fps - delaySec, preset);
}

/** Hook form of `spr` for the current frame. Returns 0 -> 1 (overshoots for playful). */
export function useSpring(preset?: SpringLike, delaySec = 0): number {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spr(frame, fps, preset, delaySec);
}
