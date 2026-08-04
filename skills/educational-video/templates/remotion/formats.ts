// Per-format layout for Remotion: 16x9, 1x1, 4x5, 9x16. One composition per format (see
// SceneFormats.tsx), one component per scene. The component asks useFormat() what it is being
// rendered into and re-blocks its layout; pixel sizes are real pixels, so a 48px label is the
// same size on a phone as on a monitor.
//
//   const f = useFormat();
//   <AbsoluteFill style={{ flexDirection: f.pick("row", "column"), padding: f.safe.px }} />
//   fontSize: f.pick(84, 72, 88)         // wide, square (also 4x5), tall
//
// 9:16 keeps clear of the platform UI (top 14 %, bottom 20 %, right 12 %); every other format
// keeps a 5 % margin. A preset can override these (theme.SAFE_AREA, see theme.ts).
import { useVideoConfig } from "remotion";

export type FormatId = "16x9" | "1x1" | "4x5" | "9x16";
export type Orientation = "wide" | "square" | "tall";
export type Margins = { top: number; bottom: number; left: number; right: number };
export type SafeOverride = Partial<Record<FormatId | "all", Partial<Margins>>>;

export const FORMAT_IDS: ReadonlyArray<FormatId> = ["16x9", "1x1", "4x5", "9x16"];

export const SIZES: Record<FormatId, { width: number; height: number }> = {
  "16x9": { width: 1920, height: 1080 },
  "1x1": { width: 1080, height: 1080 },
  "4x5": { width: 1080, height: 1350 },
  "9x16": { width: 1080, height: 1920 },
};

// Fractions of the frame kept clear.
export const SAFE: Record<FormatId, Margins> = {
  "16x9": { top: 0.05, bottom: 0.05, left: 0.05, right: 0.05 },
  "1x1": { top: 0.05, bottom: 0.05, left: 0.05, right: 0.05 },
  "4x5": { top: 0.05, bottom: 0.05, left: 0.05, right: 0.05 },
  "9x16": { top: 0.14, bottom: 0.2, left: 0.05, right: 0.12 },
};

export type Format = {
  id: FormatId;
  width: number;
  height: number;
  aspect: number;
  orientation: Orientation;
  /** Safe-area margins as fractions of the frame. */
  safeFrac: Margins;
  /** Safe-area margins in pixels, plus a ready-made CSS padding string. */
  safe: Margins & { px: string; width: number; height: number };
  /** A value per format: pick(wide, square, tall). 4x5 uses `square`. */
  pick: <T>(wide: T, square?: T, tall?: T) => T;
};

/** Composition id for a scene in a format: `Scene01` for 16x9, `Scene01-9x16` for the others. */
export function compositionId(sceneId: string, id: FormatId): string {
  return id === "16x9" ? sceneId : `${sceneId}-${id}`;
}

/** The format whose size matches width x height (falls back on aspect ratio). */
export function formatIdFromSize(width: number, height: number): FormatId {
  for (const id of FORMAT_IDS) {
    if (SIZES[id].width === width && SIZES[id].height === height) return id;
  }
  const a = width / height;
  return a > 1.2 ? "16x9" : a < 0.65 ? "9x16" : a < 0.9 ? "4x5" : "1x1";
}

export function getFormat(id: FormatId, override?: SafeOverride | null, size?: { width: number; height: number }): Format {
  const { width, height } = size ?? SIZES[id];
  const frac: Margins = { ...SAFE[id], ...(override?.all ?? {}), ...(override?.[id] ?? {}) };
  const top = Math.round(frac.top * height);
  const bottom = Math.round(frac.bottom * height);
  const left = Math.round(frac.left * width);
  const right = Math.round(frac.right * width);
  const aspect = width / height;
  return {
    id,
    width,
    height,
    aspect,
    orientation: aspect > 1.2 ? "wide" : aspect < 0.95 ? "tall" : "square",
    safeFrac: frac,
    safe: {
      top, bottom, left, right,
      px: `${top}px ${right}px ${bottom}px ${left}px`,
      width: width - left - right,
      height: height - top - bottom,
    },
    pick: <T>(wide: T, square?: T, tall?: T): T => {
      const s = square === undefined ? wide : square;
      const t = tall === undefined ? s : tall;
      return id === "16x9" ? wide : id === "9x16" ? t : s;
    },
  };
}

/** Hook form: the format of the composition being rendered, with the preset's safe-area override. */
export function useFormat(override?: SafeOverride | null): Format {
  const { width, height } = useVideoConfig();
  return getFormat(formatIdFromSize(width, height), override, { width, height });
}
