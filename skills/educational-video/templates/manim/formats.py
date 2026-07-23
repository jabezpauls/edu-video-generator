"""Per-format frame size and layout helpers for Manim.

One lesson, four shapes: 16x9, 1x1, 4x5, 9x16. Every format keeps the SAME pixels-per-unit as
16x9 (the short side is always 8 units = 1080 px), so a 48 pt label is the same size on a phone
as on a monitor. Only the frame's other side grows: 14.22 x 8 (16x9), 8 x 8 (1x1), 8 x 10
(4x5), 8 x 14.22 (9x16). Content therefore has to be re-blocked, not cropped or squeezed; the
helpers below do that.

    from formats import fmt, split, place, fit
    fmt.apply()                      # once, at the top of construct() or at import time
    split(chart, caption)            # side by side on 16x9, stacked on the tall formats
    place(title, "title")            # anchored inside the safe area, per format

The format comes from the EDU_FORMAT environment variable (render.sh sets it), default "16x9".
Safe areas: 9x16 keeps clear of the platform UI (top 14 %, bottom 20 %, right 12 %), every other
format keeps a 5 % margin. A preset may override them (see apply_preset.py -> theme.SAFE_AREA).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

UNIT = 8.0  # manim units along the short side of every format
SHORT_PX = 1080

SIZES: Dict[str, Tuple[int, int]] = {
    "16x9": (1920, 1080),
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
}

# fractions of the frame kept clear: top, bottom, left, right
SAFE: Dict[str, Tuple[float, float, float, float]] = {
    "16x9": (0.05, 0.05, 0.05, 0.05),
    "1x1": (0.05, 0.05, 0.05, 0.05),
    "4x5": (0.05, 0.05, 0.05, 0.05),
    "9x16": (0.14, 0.20, 0.05, 0.12),
}

# manim quality -> pixels on the short side (the long side follows the format's aspect)
QUALITY_SHORT_PX = {"low": 480, "med": 720, "high": 1080}


@dataclass(frozen=True)
class Format:
    id: str
    width: int
    height: int
    safe: Tuple[float, float, float, float] = (0.05, 0.05, 0.05, 0.05)

    @property
    def aspect(self) -> float:
        return self.width / self.height

    @property
    def frame_height(self) -> float:
        return UNIT if self.width >= self.height else UNIT * self.height / self.width

    @property
    def frame_width(self) -> float:
        return UNIT * self.width / self.height if self.width >= self.height else UNIT

    @property
    def orientation(self) -> str:
        return "wide" if self.aspect > 1.2 else "tall" if self.aspect < 0.95 else "square"

    @property
    def is_wide(self) -> bool:
        return self.id == "16x9"

    def pick(self, wide, square=None, tall=None):
        """A value per format: pick(wide, square, tall). 4x5 uses `square`."""
        square = wide if square is None else square
        tall = square if tall is None else tall
        return wide if self.id == "16x9" else tall if self.id == "9x16" else square

    def pixels(self, quality: str = "high") -> Tuple[int, int]:
        """Render size at a quality level (low | med | high), even-sized for H.264."""
        short = QUALITY_SHORT_PX.get(quality, SHORT_PX)
        k = short / min(self.width, self.height)
        return (round(self.width * k / 2) * 2, round(self.height * k / 2) * 2)

    def safe_bounds(self) -> Tuple[float, float, float, float]:
        """Safe area as (left, right, top, bottom) in scene coordinates (origin = frame centre)."""
        t, b, l, r = self.safe
        hw, hh = self.frame_width / 2, self.frame_height / 2
        return (-hw + l * self.frame_width, hw - r * self.frame_width,
                hh - t * self.frame_height, -hh + b * self.frame_height)

    @property
    def safe_width(self) -> float:
        left, right, _, _ = self.safe_bounds()
        return right - left

    @property
    def safe_height(self) -> float:
        _, _, top, bottom = self.safe_bounds()
        return top - bottom

    def apply(self, quality: Optional[str] = None) -> "Format":
        """Set manim's frame (units) and, if `quality` is given, its pixel size."""
        from manim import config

        config.frame_height = self.frame_height
        config.frame_width = self.frame_width
        if quality:
            config.pixel_width, config.pixel_height = self.pixels(quality)
        return self


def get(format_id: str = "16x9", safe_override: Optional[dict] = None) -> Format:
    """Look a format up by id; `safe_override` is {format_id|'all': {top,bottom,left,right}}."""
    if format_id not in SIZES:
        raise ValueError(f'unknown format "{format_id}" (use one of {", ".join(SIZES)})')
    w, h = SIZES[format_id]
    safe = SAFE[format_id]
    if safe_override:
        o = {**(safe_override.get("all") or {}), **(safe_override.get(format_id) or {})}
        safe = (o.get("top", safe[0]), o.get("bottom", safe[1]),
                o.get("left", safe[2]), o.get("right", safe[3]))
    return Format(format_id, w, h, safe)


def current() -> Format:
    """The format selected by EDU_FORMAT (default 16x9), with the preset's safe-area overrides."""
    override = None
    try:  # generated by apply_preset.py; absent in a project without a preset
        import theme  # type: ignore

        override = getattr(theme, "SAFE_AREA", None)
    except ImportError:
        pass
    return get(os.environ.get("EDU_FORMAT", "16x9"), override)


fmt = current()


# ----------------------------------------------------------------------------- layout helpers
# These need manim; they import it lazily so the module's geometry is usable without it.

def fit(mob, max_w: float = 1.0, max_h: float = 1.0, f: Optional[Format] = None):
    """Scale `mob` down (never up) to fit max_w / max_h fractions of the safe area."""
    f = f or fmt
    k = min(1.0, f.safe_width * max_w / max(mob.width, 1e-6), f.safe_height * max_h / max(mob.height, 1e-6))
    if k < 1.0:
        mob.scale(k)
    return mob


def place(mob, zone: str = "center", buff: float = 0.0, f: Optional[Format] = None):
    """Anchor `mob` to a zone of the safe area: title | caption | center | left | right."""
    from manim import DOWN, LEFT, ORIGIN, RIGHT, UP
    import numpy as np

    f = f or fmt
    left, right, top, bottom = f.safe_bounds()
    cx, cy = (left + right) / 2, (top + bottom) / 2
    fit(mob, f=f)
    if zone == "title":
        mob.move_to(np.array([cx, 0, 0])).align_to(np.array([0, top - buff, 0]), UP)
    elif zone == "caption":
        mob.move_to(np.array([cx, 0, 0])).align_to(np.array([0, bottom + buff, 0]), DOWN)
    elif zone == "left":
        mob.move_to(np.array([left + mob.width / 2 + buff, cy, 0]))
    elif zone == "right":
        mob.move_to(np.array([right - mob.width / 2 - buff, cy, 0]))
    elif zone == "center":
        mob.move_to(np.array([cx, cy, 0]))
    else:
        raise ValueError(f'unknown zone "{zone}"')
    return mob


def split(a, b, buff: float = 0.5, f: Optional[Format] = None):
    """Two blocks: side by side on 16x9, stacked on 1x1 / 4x5 / 9x16. Returns the VGroup,
    centred in the safe area and scaled to fit it."""
    from manim import DOWN, RIGHT, VGroup

    f = f or fmt
    g = VGroup(a, b).arrange(RIGHT if f.is_wide else DOWN, buff=buff)
    fit(g, f=f)
    return place(g, "center", f=f)


def stack(*mobs, buff: float = 0.4, f: Optional[Format] = None):
    """Vertical stack (every format), centred in the safe area and fitted to it."""
    from manim import DOWN, VGroup

    f = f or fmt
    g = VGroup(*mobs).arrange(DOWN, buff=buff)
    fit(g, f=f)
    return place(g, "center", f=f)


def row_or_column(*mobs, buff: float = 0.5, f: Optional[Format] = None):
    """Row on 16x9, column elsewhere, centred in the safe area and fitted to it."""
    from manim import DOWN, RIGHT, VGroup

    f = f or fmt
    g = VGroup(*mobs).arrange(RIGHT if f.is_wide else DOWN, buff=buff)
    fit(g, f=f)
    return place(g, "center", f=f)
