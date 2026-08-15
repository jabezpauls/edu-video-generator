"""Read narration-grid cues from a Manim scene (copy to <project>/scenes/gridsync.py).

    from gridsync import GridScene

    class Scene01(GridScene):
        SCENE_ID = "01"
        def construct(self):
            eq = MathTex(r"i \cdot z")
            self.play(Write(eq), run_time=0.6)
            self.wait_until("rotates")                 # hold until the word is spoken
            self.play(Rotate(dot, PI / 2, about_point=ORIGIN), run_time=0.8)
            self.finish()                              # hold to the end of the scene's slot

Anchors are the same as storyboard `on` values: "rotates", "rotates#2", "w12", "p2", "end",
or a qualified "s02.start". Times come from grid.json (written by scripts/grid.py), so the
picture lands on the word exactly as the narration (and the sound effects) do.
"""
import json
from pathlib import Path

from manim import Scene

HIT_LEAD = 0.06   # start visuals this long before the word so they read on it


class Grid:
    def __init__(self, scene_id, path=None):
        path = Path(path) if path else Path(__file__).resolve().parent.parent / "grid.json"
        self.data = json.loads(path.read_text())
        self.scene = next(s for s in self.data["scenes"] if s["id"] == str(scene_id))
        self.start = self.scene["start"]
        self.duration = self.scene["duration"]
        self.fps = self.data.get("fps", 30)

    def cue(self, anchor):
        """Seconds from the start of THIS scene's slot to the anchor."""
        name = anchor.lower()
        cues = self.data["cues"]
        if name.startswith("s") and "." in name:          # qualified: "s02.start"
            qual, _, name = name.partition(".")
            prefix = f"s{int(qual[1:]):02d}"
        else:
            prefix = f"s{self.scene['n']:02d}"
        base, _, nth = name.partition("#")
        # start / end / wN / pN are reserved: the word of that name is reached as "end#1"
        reserved = base in ("start", "end") or (base[:1] in "wp" and base[1:].isdigit())
        key = f"{prefix}.{base}#{nth}" if nth and (nth != "1" or reserved) else f"{prefix}.{base}"
        if key not in cues:
            raise KeyError(f"no cue {anchor!r} (looked for {key!r}) in scene {self.scene['id']}")
        return cues[key] - self.start


class GridScene(Scene):
    SCENE_ID = None

    def setup(self):
        super().setup()
        self.grid = Grid(self.SCENE_ID)

    @property
    def now(self):
        return self.renderer.time

    def wait_until(self, anchor, lead=HIT_LEAD):
        """Hold until `lead` seconds before the anchored word; no-op if it is already past."""
        dt = self.grid.cue(anchor) - lead - self.now
        if dt > 1.0 / self.camera.frame_rate:
            self.wait(dt)
        return self

    def finish(self):
        """Hold to the end of this scene's slot so the render matches the grid duration."""
        dt = self.grid.duration - self.now
        if dt > 1.0 / self.camera.frame_rate:
            self.wait(dt)
