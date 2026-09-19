#!/usr/bin/env python3
"""Apply a look-and-feel preset to a video project.

Usage: apply_preset.py <preset> <project-dir> [--presets-dir DIR]

<preset> is a name (looked up in <project>/presets/, then the skill's presets/) or a path to a
preset folder. A preset folder holds preset.jsonc (see presets/blank for every field) and its
fonts. Writes, inside the project:

  preset.json               the resolved preset, defaults filled in
  assets/fonts/             display.woff2/.ttf and body.woff2/.ttf, copied from the preset
  scenes/theme.py           palette, font names, safe area and helpers for Manim scenes
  scenes/src/theme.ts       palette, CSS variables, font loading and safe area for Remotion scenes
  scenes/public/fonts/      the .woff2 files Remotion serves with staticFile()
  manifest.json             "preset" set, if a manifest exists

A motion-engine project (film/index.html exists) only gets preset.json and assets/fonts/: the film reads
those through sync.mjs (window.PRESET), so run sync.mjs or render.sh afterwards. The theme files above are
left out of it.

Safe to re-run; a changed preset just rewrites the generated files.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent

DEFAULT_COLORS = {
    "bg": "#0e1116",
    "ink": "#e6edf3",
    "ink2": "#9aa7b4",
    "accent": "#58a6ff",
    "highlight": "#f78166",
    "card": "#161b22",
}
SYSTEM_STACK = 'system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif'
MOODS = ("", "calm", "curious", "upbeat", "none")
CAPTION_STYLES = ("", "pill", "outline", "plain")
CAPTION_POSITIONS = ("", "bottom", "center")
ACTIVE_WORD = ("", "accent", "highlight")
FORMATS = ("16x9", "1x1", "4x5", "9x16")
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class PresetError(Exception):
    pass


def parse_jsonc(src: str):
    """JSON with // and /* */ comments and trailing commas. String-aware, so URLs survive."""
    out, i, n, in_str = [], 0, len(src), False
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if in_str:
            out.append(c)
            if c == "\\":
                out.append(nxt)
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
        elif c == "/" and nxt == "*":
            end = src.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            out.append(c)
            i += 1
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))


def find_preset(name: str, project: Path, extra: Path | None) -> Path:
    p = Path(name)
    if (p / "preset.jsonc").is_file():
        return p.resolve()
    roots = [project / "presets", *([extra] if extra else []), SKILL / "presets"]
    for root in roots:
        if (root / name / "preset.jsonc").is_file():
            return (root / name).resolve()
    have = sorted({d.name for r in roots if r.is_dir() for d in r.iterdir() if (d / "preset.jsonc").is_file()})
    raise PresetError(f'no preset "{name}" (have: {", ".join(have) or "none"})')


def filled(v) -> bool:
    return v is not None and v != "" and v != [] and v != {}


def resolve(raw: dict, folder: Path) -> dict:
    """Validate a parsed preset and fill defaults. Font paths become absolute."""
    r: dict = {"name": raw.get("name") or folder.name, "description": raw.get("description") or ""}

    colors = dict(DEFAULT_COLORS)
    for k, v in (raw.get("colors") or {}).items():
        if k not in DEFAULT_COLORS:
            raise PresetError(f'colors.{k}: unknown token (use {", ".join(DEFAULT_COLORS)})')
        if filled(v):
            if not isinstance(v, str) or not HEX.match(v):
                raise PresetError(f'colors.{k}: "{v}" is not a hex colour like #1f2a24')
            colors[k] = v.lower()
    r["colors"] = colors

    fonts = {}
    for role in ("display", "body"):
        f = (raw.get("fonts") or {}).get(role) or {}
        out = {"family": f.get("family") or "", "weight": f.get("weight") or 400,
               "tracking": f.get("tracking") or "", "woff2": None, "ttf": None}
        for key, dest in (("file", "woff2"), ("ttf", "ttf")):
            if filled(f.get(key)):
                path = (folder / f[key]).resolve()
                if not path.is_file():
                    raise PresetError(f"fonts.{role}.{key}: {path} does not exist")
                out[dest] = str(path)
        if (out["woff2"] or out["ttf"]) and not out["family"]:
            raise PresetError(f"fonts.{role}.family is required when a font file is given")
        fonts[role] = out
    r["fonts"] = fonts

    v = raw.get("voice") or {}
    r["voice"] = {k: v.get(k) or "" for k in ("elevenlabs", "openai", "piper", "style")}

    m = raw.get("music") or {}
    if (m.get("mood") or "") not in MOODS:
        raise PresetError(f'music.mood: "{m.get("mood")}" (use calm, curious, upbeat or none)')
    r["music"] = {"mood": m.get("mood") or "", "level_db": m.get("level_db") or 0}
    s = raw.get("sfx") or {}
    r["sfx"] = {"enabled": s.get("enabled", True) is not False, "level_db": s.get("level_db") or 0}

    c = raw.get("captions") or {}
    for key, allowed in (("style", CAPTION_STYLES), ("position", CAPTION_POSITIONS), ("active_word", ACTIVE_WORD)):
        if (c.get(key) or "") not in allowed:
            raise PresetError(f'captions.{key}: "{c.get(key)}" (use {", ".join(a for a in allowed if a)})')
    r["captions"] = {k: c.get(k) or "" for k in ("style", "position", "active_word")}

    cards = raw.get("cards") or {}
    r["cards"] = {
        side: {"text": (cards.get(side) or {}).get("text") or "", "subtitle": (cards.get(side) or {}).get("subtitle") or ""}
        for side in ("intro", "outro")
    }

    safe = {}
    for fid, margins in (raw.get("safe_area") or {}).items():
        if fid != "all" and fid not in FORMATS:
            raise PresetError(f'safe_area.{fid}: unknown format (use all, {", ".join(FORMATS)})')
        clean = {}
        for side, val in (margins or {}).items():
            if side not in ("top", "bottom", "left", "right"):
                raise PresetError(f"safe_area.{fid}.{side}: unknown side")
            if not isinstance(val, (int, float)) or not 0 <= val < 0.5:
                raise PresetError(f"safe_area.{fid}.{side}: must be a fraction from 0 to 0.5")
            clean[side] = val
        safe[fid] = clean
    r["safe_area"] = safe
    r["notes"] = [str(n) for n in (raw.get("notes") or [])]
    return r


# ----------------------------------------------------------------------------- generated files
def theme_py(p: dict, font_files: dict) -> str:
    c = p["colors"]
    return f'''"""Generated by apply_preset.py from preset "{p["name"]}". Edit the preset, not this file."""
from pathlib import Path

PRESET = {p["name"]!r}
PALETTE = {c!r}
BG, INK, INK2, ACCENT, HIGHLIGHT, CARD = (PALETTE[k] for k in ("bg", "ink", "ink2", "accent", "highlight", "card"))

# Family names as Pango knows them ("" = Manim's default font).
FONT_DISPLAY = {p["fonts"]["display"]["family"] if font_files.get("display") else ""!r}
FONT_BODY = {p["fonts"]["body"]["family"] if font_files.get("body") else ""!r}
_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_FILES = [str(_FONTS / n) for n in {[Path(f).name for f in font_files.values()]!r}]

SAFE_AREA = {p["safe_area"]!r}
CAPTIONS = {p["captions"]!r}
CARDS = {p["cards"]!r}

_registered = False


def register_fonts():
    """Make the preset's fonts visible to Pango (once per process)."""
    global _registered
    if _registered or not FONT_FILES:
        return
    import manimpango

    for f in FONT_FILES:
        manimpango.register_font(f)
    _registered = True


def setup(scene):
    """Call first in construct(): background colour, fonts and the frame for EDU_FORMAT."""
    register_fonts()
    scene.camera.background_color = BG
    try:
        from formats import fmt

        fmt.apply()
    except ImportError:
        pass
    return scene


def title(text, **kw):
    from manim import Text

    register_fonts()
    kw.setdefault("font_size", 72)
    kw.setdefault("color", INK)
    if FONT_DISPLAY:
        kw.setdefault("font", FONT_DISPLAY)
    return Text(text, **kw)


def body(text, **kw):
    from manim import Text

    register_fonts()
    kw.setdefault("font_size", 40)
    kw.setdefault("color", INK2)
    if FONT_BODY:
        kw.setdefault("font", FONT_BODY)
    return Text(text, **kw)


def eq(tex, **kw):
    """MathTex in the preset's ink colour. LaTeX keeps its own math fonts."""
    from manim import MathTex

    kw.setdefault("color", INK)
    return MathTex(tex, **kw)
'''


def theme_ts(p: dict, font_files: dict) -> str:
    c = p["colors"]
    faces = []
    for role in ("display", "body"):
        f = p["fonts"][role]
        if font_files.get(role) and f["woff2"]:
            faces.append({"role": role, "family": f["family"], "weight": f["weight"]})
    stack = {r: (f'"{p["fonts"][r]["family"]}", {SYSTEM_STACK}' if any(x["role"] == r for x in faces) else SYSTEM_STACK)
             for r in ("display", "body")}
    return f'''// Generated by apply_preset.py from preset "{p["name"]}". Edit the preset, not this file.
import {{ cancelRender, continueRender, delayRender, staticFile }} from "remotion";
import type React from "react";
import type {{ SafeOverride }} from "./formats";

export const PRESET = {json.dumps(p["name"])};

export const COLORS = {json.dumps(c, indent=2)} as const;

/** Spread into a root element's style, then use var(--bg), var(--ink), ... below it. */
export const themeVars = {{
  "--bg": COLORS.bg,
  "--ink": COLORS.ink,
  "--ink-2": COLORS.ink2,
  "--accent": COLORS.accent,
  "--highlight": COLORS.highlight,
  "--card": COLORS.card,
  "--font-display": {json.dumps(stack["display"])},
  "--font-body": {json.dumps(stack["body"])},
}} as React.CSSProperties;

export const FONTS = {{
  display: {{ family: {json.dumps(stack["display"])}, weight: {p["fonts"]["display"]["weight"]}, tracking: {json.dumps(p["fonts"]["display"]["tracking"])} }},
  body: {{ family: {json.dumps(stack["body"])}, weight: {p["fonts"]["body"]["weight"]} }},
}} as const;

export const SAFE_AREA: SafeOverride = {json.dumps(p["safe_area"])};
export const CAPTIONS = {json.dumps(p["captions"])} as const;
export const CARDS = {json.dumps(p["cards"])} as const;

const FACES: ReadonlyArray<{{ family: string; weight: number; file: string }}> = [
{"".join(f'  {{ family: {json.dumps(x["family"])}, weight: {x["weight"]}, file: "fonts/{x["role"]}.woff2" }},' + chr(10) for x in faces)}];

// Block rendering until the preset's fonts are loaded, so no frame is drawn in a fallback face.
if (typeof document !== "undefined" && FACES.length > 0) {{
  const handle = delayRender("preset fonts");
  Promise.all(
    FACES.map((f) =>
      new FontFace(f.family, `url(${{staticFile(f.file)}}) format("woff2")`, {{ weight: "100 900" }})
        .load()
        .then((face) => document.fonts.add(face)),
    ),
  )
    .then(() => continueRender(handle))
    .catch((err) => cancelRender(err));
}}
'''


def is_motion_project(project: Path) -> bool:
    return (project / "film" / "index.html").is_file() and not (project / "scenes" / "package.json").is_file()


def apply(preset: str, project: Path, presets_dir: Path | None = None) -> dict:
    project = project.resolve()
    folder = find_preset(preset, project, presets_dir)
    p = resolve(parse_jsonc((folder / "preset.jsonc").read_text(encoding="utf-8")), folder)

    motion = is_motion_project(project)
    fonts_dir = project / "assets" / "fonts"
    web_dir = project / "scenes" / "public" / "fonts"
    ttf_files, woff_files = {}, {}
    for role in ("display", "body"):
        f = p["fonts"][role]
        for kind, dest_dir in (("ttf", fonts_dir), ("woff2", fonts_dir)):
            if f[kind] and not (motion and kind == "ttf"):
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / f"{role}.{kind}"
                shutil.copyfile(f[kind], dest)
        if f["woff2"] and not motion:
            web_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f["woff2"], web_dir / f"{role}.woff2")
            woff_files[role] = web_dir / f"{role}.woff2"
        if f["ttf"] and not motion:
            ttf_files[role] = fonts_dir / f"{role}.ttf"

    if not is_motion_project(project):
        scenes = project / "scenes"
        scenes.mkdir(parents=True, exist_ok=True)
        (scenes / "theme.py").write_text(theme_py(p, ttf_files), encoding="utf-8")
        (scenes / "src").mkdir(parents=True, exist_ok=True)
        (scenes / "src" / "theme.ts").write_text(theme_ts(p, woff_files), encoding="utf-8")

    resolved = {**p, "fonts": {k: {**v, "woff2": f"assets/fonts/{k}.woff2" if v["woff2"] else None,
                                   "ttf": f"assets/fonts/{k}.ttf" if v["ttf"] and not motion else None}
                               for k, v in p["fonts"].items()}}
    (project / "preset.json").write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")

    manifest = project / "manifest.json"
    if manifest.is_file():
        m = json.loads(manifest.read_text(encoding="utf-8"))
        m["preset"] = folder.name
        manifest.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    return resolved


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("preset")
    ap.add_argument("project")
    ap.add_argument("--presets-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    try:
        r = apply(a.preset, Path(a.project), a.presets_dir)
    except PresetError as e:
        print(f"apply_preset: {e}", file=sys.stderr)
        return 1
    fonts = ", ".join(f'{k}={v["family"]}' for k, v in r["fonts"].items() if v["family"]) or "system fonts"
    print(f'preset "{r["name"]}" applied to {a.project} ({fonts})')
    return 0


if __name__ == "__main__":
    sys.exit(main())
