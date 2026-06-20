#!/usr/bin/env python3
"""Validate storyboard.json. Exits non-zero with field errors if invalid.

Uses jsonschema if available; otherwise falls back to a built-in structural check
(no extra install needed). Usage: validate_storyboard.py <project-dir>
"""
import json
import os
import sys

ALLOWED_POS = {"center", "top", "bottom", "left", "right",
               "top-left", "top-right", "bottom-left", "bottom-right"}
ALLOWED_KIND = {"equation", "text", "shape", "image", "code", "chart", "axes"}


def fail(errs):
    for e in errs:
        print(f"  - {e}", file=sys.stderr)
    print(f"storyboard INVALID ({len(errs)} error(s))", file=sys.stderr)
    sys.exit(1)


def manual_check(sb) -> list:
    errs = []
    req_top = ["title", "engine", "fps", "target_duration_s", "scenes"]
    for k in req_top:
        if k not in sb:
            errs.append(f"missing top-level field: {k}")
    if sb.get("engine") not in ("manim", "remotion", None):
        errs.append(f"engine must be manim|remotion, got {sb.get('engine')!r}")
    scenes = sb.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        errs.append("scenes must be a non-empty array")
        return errs
    ids = set()
    total = 0.0
    for i, sc in enumerate(scenes):
        loc = f"scene[{i}]"
        for k in ("id", "narration", "elements", "beats", "est_duration_s"):
            if k not in sc:
                errs.append(f"{loc}: missing field {k}")
        sid = sc.get("id")
        if sid in ids:
            errs.append(f"{loc}: duplicate id {sid!r}")
        ids.add(sid)
        total += float(sc.get("est_duration_s", 0) or 0)
        for j, el in enumerate(sc.get("elements", []) or []):
            if el.get("kind") not in ALLOWED_KIND:
                errs.append(f"{loc}.elements[{j}]: bad kind {el.get('kind')!r}")
            if "position" in el and el["position"] not in ALLOWED_POS:
                errs.append(f"{loc}.elements[{j}]: bad position {el.get('position')!r}")
        beats = sc.get("beats", []) or []
        last_t = -1.0
        for j, b in enumerate(beats):
            if "t" not in b or "action" not in b:
                errs.append(f"{loc}.beats[{j}]: needs t and action")
                continue
            if float(b["t"]) < last_t:
                errs.append(f"{loc}.beats[{j}]: t not in ascending order")
            last_t = float(b["t"])
    target = float(sb.get("target_duration_s", 0) or 0)
    if target > 0:
        lo, hi = target * 0.85, target * 1.15
        if not (lo <= total <= hi):
            errs.append(f"sum of est_duration_s ({total:.0f}s) outside +/-15% of "
                        f"target ({target:.0f}s)")
    return errs


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

    errs = manual_check(sb)
    if errs:
        fail(errs)
    print(f"storyboard OK: {len(sb['scenes'])} scenes, "
          f"~{sum(float(s.get('est_duration_s',0) or 0) for s in sb['scenes']):.0f}s, "
          f"engine={sb.get('engine')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
