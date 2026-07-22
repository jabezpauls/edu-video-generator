"""Closed-form springs for Manim, as rate functions.

The same four presets and the same maths as the Remotion helper (springs.ts) and the motion
engine, so a lesson moves the same way whichever engine draws it.

    from springs import spring, settle

    self.play(obj.animate.shift(RIGHT * 2), rate_func=spring("snappy"), run_time=settle("snappy"))
    self.play(FadeIn(title, shift=UP * 0.3), rate_func=spring("heavy"), run_time=settle("heavy"))

A spring rate function maps alpha in [0, 1] onto the spring's unit step response, stretched over
the animation's run_time and normalised so alpha = 1 lands exactly on 1.0. With run_time =
settle(name) the curve is the true spring; a longer run_time just slows it down.

Overshooting presets (snappy, default barely; playful clearly) return values above 1 mid-way.
That is fine for move / scale / shift / rotate / fade. Avoid `playful` on Create, Write and
DrawBorderThenFill, which expect alpha to stay inside [0, 1].
"""
from __future__ import annotations

import math
from typing import Callable, Dict, Optional, Union

# response: seconds for one undamped period; damping: ratio zeta.
PRESETS: Dict[str, Dict[str, float]] = {
    "snappy": {"response": 0.22, "damping": 0.8},  # ~1.5% overshoot - toggles, leading edges
    "default": {"response": 0.4, "damping": 0.86},  # ~0.5% overshoot - cards, containers
    "heavy": {"response": 0.5, "damping": 1.0},  # none (critical) - big type, titles
    "playful": {"response": 0.5, "damping": 0.45},  # ~20% overshoot - one-off emphasis
}

Preset = Union[str, Dict[str, float], None]


def resolve(preset: Preset = None) -> Dict[str, float]:
    if preset is None:
        return PRESETS["default"]
    if isinstance(preset, str):
        try:
            return PRESETS[preset]
        except KeyError:
            raise ValueError(f'springs: unknown preset "{preset}"') from None
    return preset


def step(tau: float, preset: Preset = None) -> float:
    """Unit step response of a spring released tau seconds ago. 0 for tau <= 0."""
    if not tau > 0:
        return 0.0
    p = resolve(preset)
    z = p["damping"]
    w = 2 * math.pi / p["response"]
    if z < 1:
        wd = w * math.sqrt(1 - z * z)
        return 1 - math.exp(-z * w * tau) * (
            math.cos(wd * tau) + (z * w / wd) * math.sin(wd * tau)
        )
    if z == 1:
        return 1 - math.exp(-w * tau) * (1 + w * tau)
    wd = w * math.sqrt(z * z - 1)  # overdamped
    return 1 - math.exp(-z * w * tau) * (
        math.cosh(wd * tau) + (z * w / wd) * math.sinh(wd * tau)
    )


_settle_cache: Dict[tuple, float] = {}


def settle(preset: Preset = None, eps: float = 0.01) -> float:
    """Seconds until the response stays within eps of its target for good.

    Use it as run_time so the animation plays the true spring.
    """
    p = resolve(preset)
    key = (p["response"], p["damping"], eps)
    if key not in _settle_cache:
        last = 0.0
        n = int(20 * p["response"] / 0.001) + 1
        for i in range(n):
            tau = i * 0.001
            if abs(1 - step(tau, p)) >= eps:
                last = tau
        _settle_cache[key] = last
    return _settle_cache[key]


def spring(preset: Preset = None, eps: float = 0.01) -> Callable[[float], float]:
    """A Manim rate function: alpha in [0, 1] -> spring response, with spring(1) == 1 exactly."""
    p = resolve(preset)
    duration = settle(p, eps)
    end = step(duration, p)

    def rate(alpha: float) -> float:
        if alpha <= 0:
            return 0.0
        if alpha >= 1:
            return 1.0
        return step(alpha * duration, p) / end

    return rate


def spring_at(t: float, t0: float, start: float, end: float, preset: Preset = None) -> float:
    """One spring from start to end released at t0 seconds, evaluated at t (for updaters)."""
    return start + (end - start) * step(t - t0, preset)
