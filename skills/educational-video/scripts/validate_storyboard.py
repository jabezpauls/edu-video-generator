#!/usr/bin/env python3
"""Validate storyboard.json. Exits non-zero with field errors if invalid.

Pure-stdlib structural check (no extra install needed). The checks are exposed as
functions (`check`, `manual_check`) so they can be unit-tested and reused.

Usage: validate_storyboard.py <project-dir>
"""
import json
import os
import sys

ALLOWED_POS = {"center", "top", "bottom", "left", "right",
               "top-left", "top-right", "bottom-left", "bottom-right"}
ALLOWED_KIND = {"equation", "text", "shape", "image", "code", "chart", "axes"}
ENGINES = ("manim", "remotion")


def fail(errs):
    for e in errs:
        print(f"  - {e}", file=sys.stderr)
    print(f"storyboard INVALID ({len(errs)} error(s))", file=sys.stderr)
    sys.exit(1)


def _num(value):
    """Return value as float, or None if it is not a real number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def check(sb) -> tuple:
    """Return (errors, warnings) for a parsed storyboard."""
    errs, warns = [], []
    if not isinstance(sb, dict):
        return ["storyboard must be a JSON object"], warns

    for k in ("title", "engine", "fps", "target_duration_s", "scenes"):
        if k not in sb:
            errs.append(f"missing top-level field: {k}")
    if sb.get("engine") not in (*ENGINES, None):
        errs.append(f"engine must be {'|'.join(ENGINES)}, got {sb.get('engine')!r}")

    scenes = sb.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        errs.append("scenes must be a non-empty array")
        return errs, warns

    ids = set()
    total = 0.0
    for i, sc in enumerate(scenes):
        loc = f"scene[{i}]"
        if not isinstance(sc, dict):
            errs.append(f"{loc}: must be an object")
            continue
        for k in ("id", "narration", "elements", "beats", "est_duration_s"):
            if k not in sc:
                errs.append(f"{loc}: missing field {k}")
        sid = sc.get("id")
        if sid in ids:
            errs.append(f"{loc}: duplicate id {sid!r}")
        ids.add(sid)

        est = sc.get("est_duration_s", 0)
        if est is None:
            est = 0
        if _num(est) is None:
            errs.append(f"{loc}: est_duration_s must be a number, got {est!r}")
        else:
            total += _num(est)

        for j, el in enumerate(sc.get("elements", []) or []):
            if not isinstance(el, dict):
                errs.append(f"{loc}.elements[{j}]: must be an object")
                continue
            if el.get("kind") not in ALLOWED_KIND:
                errs.append(f"{loc}.elements[{j}]: bad kind {el.get('kind')!r}")
            if "position" in el and el["position"] not in ALLOWED_POS:
                errs.append(f"{loc}.elements[{j}]: bad position {el.get('position')!r}")

        last_t = -1.0
        for j, b in enumerate(sc.get("beats", []) or []):
            bloc = f"{loc}.beats[{j}]"
            if not isinstance(b, dict):
                errs.append(f"{bloc}: must be an object")
                continue
            if "t" not in b or "action" not in b:
                errs.append(f"{bloc}: needs t and action")
                continue
            t = _num(b["t"])
            if t is None:
                errs.append(f"{bloc}: t must be a number, got {b['t']!r}")
                continue
            if t < last_t:
                errs.append(f"{bloc}: t not in ascending order")
            last_t = t

    target = _num(sb.get("target_duration_s", 0)) or 0.0
    if target > 0:
        lo, hi = target * 0.85, target * 1.15
        if not (lo <= total <= hi):
            errs.append(f"sum of est_duration_s ({total:.0f}s) outside +/-15% of "
                        f"target ({target:.0f}s)")
    return errs, warns


def manual_check(sb) -> list:
    """Errors only (kept for callers that don't care about warnings)."""
    return check(sb)[0]


def main() -> int:
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    path = os.path.join(project, "storyboard.json")
    if not os.path.isfile(path):
        print(f"not found: {path}", file=sys.stderr)
        return 1
    with open(path) as f:
        try:
            sb = json.load(f)
        except json.JSONDecodeError as e:
            fail([f"JSON parse error: {e}"])

    errs, warns = check(sb)
    for w in warns:
        print(f"  warning: {w}", file=sys.stderr)
    if errs:
        fail(errs)
    total = sum(float(s.get("est_duration_s", 0) or 0) for s in sb["scenes"])
    print(f"storyboard OK: {len(sb['scenes'])} scenes, ~{total:.0f}s, "
          f"engine={sb.get('engine')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
