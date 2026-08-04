// Registers one scene as one composition per format. In src/Root.tsx:
//
//   <SceneFormats id="Scene01" component={Scene01} seconds={12} />
//
// Composition ids: Scene01 (16x9), Scene01-1x1, Scene01-4x5, Scene01-9x16. Render one with
//   render.sh remotion <project> 01 high 9x16
import React from "react";
import { Composition } from "remotion";
import { FORMAT_IDS, SIZES, compositionId, type FormatId } from "./formats";

type Props = {
  id: string;
  component: React.ComponentType<any>;
  seconds: number;
  fps?: number;
  /** Subset of formats to register; default all four. */
  formats?: ReadonlyArray<FormatId>;
  defaultProps?: Record<string, unknown>;
};

export const SceneFormats: React.FC<Props> = ({ id, component, seconds, fps = 30, formats = FORMAT_IDS, defaultProps }) => (
  <>
    {formats.map((f) => (
      <Composition
        key={f}
        id={compositionId(id, f)}
        component={component}
        durationInFrames={Math.max(1, Math.round(seconds * fps))}
        fps={fps}
        width={SIZES[f].width}
        height={SIZES[f].height}
        defaultProps={defaultProps}
      />
    ))}
  </>
);
