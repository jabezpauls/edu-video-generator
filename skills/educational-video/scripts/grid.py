#!/usr/bin/env python3
"""Narration grid: one word-level timeline that picture and sound share.

Reads storyboard.json and each scene's narration audio/words, and writes <project>/grid.json:
scene start/end (with lead-in and tail padding), every spoken word on the global clock, and
named cues in seconds:

  s03.start          start of scene 3 (before the lead-in)
  s03.end            end of the speech in scene 3
  s03.w12            word index 12 (zero-based)
  s03.derivative     first occurrence of "derivative"; s03.derivative#2 the second
  s03.p2             start of sentence/phrase 2 (one-based)

Usage:
  grid.py [build] <project> [--lead S] [--tail S] [--min-scene S] [--no-asr] [--write-durations]
  grid.py resolve <project>        beat `on` anchors -> beats.resolved.json
  grid.py cue <project> <cue>      print one cue's time (e.g. s02.derivative#2)
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wordtimes as wt  # noqa: E402

VERSION = 1
DEFAULT_LEAD = 0.4       # silence before the first word of a scene
DEFAULT_TAIL = 0.6       # silence after the last word (room for the visual to land)
DEFAULT_MIN_SCENE = 1.5
HIT_LEAD = 0.06          # visuals should start this much before a cue so they read on the word
SPECIALS = ("start", "end")

_ANCHOR = re.compile(r"^(?:s(?P<scene>\d+)\.)?(?P<name>[^#]+?)(?:#(?P<nth>\d+))?$")


class GridError(ValueError):
    pass


def scene_number(sid, index):
    return int(sid) if str(sid).isdigit() else index + 1


def _cue_prefix(n):
    return f"s{n:02d}"


def build(sb, words_for, lead=DEFAULT_LEAD, tail=DEFAULT_TAIL, min_scene=DEFAULT_MIN_SCENE):
    """Build the grid dict.

    `words_for(scene) -> (words, source, audio_seconds)` supplies per-scene words (scene-local
    seconds, one per narration token) and the audio length. Pure; no file access.
    """
    narrated = sb.get("narration", True) is not False
    scenes, cues, t0 = [], {}, 0.0
    for idx, sc in enumerate(sb["scenes"]):
        sid = str(sc["id"])
        n = scene_number(sid, idx)
        text = (sc.get("narration") or "").strip()
        words, source, audio_s = ([], "none", 0.0)
        if text:
            words, source, audio_s = words_for(sc)
        speech_end = max([w["end"] for w in words] + [audio_s]) if words else 0.0
        if narrated and words:
            duration = max(min_scene, lead + speech_end + tail)
        else:
            duration = max(min_scene, float(sc.get("est_duration_s") or 0))
        pre = lead if words else 0.0

        out_words, phrases, seen = [], [], {}
        phrase_no, phrase_open = 1, True
        for i, w in enumerate(words):
            gw = {"i": i, "word": w["word"], "norm": wt.norm(w["word"]),
                  "start": round(t0 + pre + w["start"], 4), "end": round(t0 + pre + w["end"], 4),
                  "phrase": phrase_no}
            out_words.append(gw)
            if phrase_open:
                phrases.append({"i": phrase_no, "start": gw["start"], "end": gw["end"], "text": ""})
                phrase_open = False
            phrases[-1]["end"] = gw["end"]
            phrases[-1]["text"] = (phrases[-1]["text"] + " " + w["word"]).strip()
            if wt.ends_sentence(w["word"]):
                phrase_no += 1
                phrase_open = True
        pfx = _cue_prefix(n)
        cues[f"{pfx}.start"] = round(t0, 4)
        for gw in out_words:
            cues[f"{pfx}.w{gw['i']}"] = gw["start"]
            k = seen[gw["norm"]] = seen.get(gw["norm"], 0) + 1
            name = gw["norm"]
            if name in SPECIALS or re.fullmatch(r"[wp]\d+", name):
                name += "#1"  # keep reserved names reachable: end#1, w3#1
            cues[f"{pfx}.{name}" if k == 1 else f"{pfx}.{gw['norm']}#{k}"] = gw["start"]
        for ph in phrases:
            cues[f"{pfx}.p{ph['i']}"] = ph["start"]
        s_end = out_words[-1]["end"] if out_words else round(t0 + duration, 4)
        s_end = max(s_end, round(t0 + pre + audio_s, 4)) if out_words else s_end
        cues[f"{pfx}.end"] = round(s_end, 4)
        scenes.append({
            "id": sid, "n": n, "start": round(t0, 4), "end": round(t0 + duration, 4),
            "duration": round(duration, 4),
            "speech_start": out_words[0]["start"] if out_words else None,
            "speech_end": s_end if out_words else None,
            "audio": f"audio/scene_{sid}.wav" if audio_s else None,
            "words_source": source, "words": out_words, "phrases": phrases,
        })
        t0 += duration
    return {"version": VERSION, "lead": lead, "tail": tail, "hit_lead": HIT_LEAD,
            "fps": sb.get("fps", 30), "duration": round(t0, 4), "scenes": scenes, "cues": cues}


def _find_scene(grid, ref):
    ref = str(ref)
    for sc in grid["scenes"]:
        if sc["id"] == ref:
            return sc
    if ref.isdigit():
        for sc in grid["scenes"]:
            if sc["n"] == int(ref):
                return sc
    return None


def resolve(grid, anchor, scene_id=None):
    """Resolve an `on` anchor to global seconds. Unqualified anchors need `scene_id`."""
    m = _ANCHOR.match(anchor.strip()) if isinstance(anchor, str) else None
    if not m:
        raise GridError(f"bad anchor {anchor!r}")
    sc = _find_scene(grid, m["scene"]) if m["scene"] else _find_scene(grid, scene_id)
    if sc is None:
        raise GridError(f"anchor {anchor!r}: unknown scene {m['scene'] or scene_id!r}")
    name, nth = m["name"].lower(), m["nth"]
    pfx = _cue_prefix(sc["n"])
    cues = grid["cues"]
    if nth is None and name in SPECIALS:
        return cues[f"{pfx}.{name}"]
    if nth is None and re.fullmatch(r"[wp]\d+", name):
        key = f"{pfx}.{name}"
        if key not in cues:
            kind = "word" if name[0] == "w" else "phrase"
            raise GridError(f"{anchor!r}: scene {sc['id']} has no {kind} {name[1:]}")
        return cues[key]
    word = wt.norm(name)
    k = int(nth) if nth else 1
    reserved = word in SPECIALS or re.fullmatch(r"[wp]\d+", word)
    key = f"{pfx}.{word}#{k}" if (k > 1 or reserved) else f"{pfx}.{word}"
    if key not in cues and k == 1:
        key = f"{pfx}.{word}"  # "word#1" is an alias for the plain word cue
    if key not in cues:
        heard = sum(1 for w in sc["words"] if w["norm"] == word)
        raise GridError(f"anchor {anchor!r}: scene {sc['id']} says {word!r} {heard} time(s)"
                        if heard else f"anchor {anchor!r}: {word!r} is not in scene {sc['id']}'s narration")
    return cues[key]


def resolve_beats(sb, grid):
    """Beat times for every scene. `on` wins over `t` when it resolves.

    Returns {"scenes": [{id, start, duration, beats: [{action, target, t, at, source, on?}]}]}
    with `t` in scene-local seconds and `at` on the global clock. Raises GridError listing every
    anchor that cannot be resolved.
    """
    problems, out = [], []
    for sc in sb["scenes"]:
        gsc = _find_scene(grid, sc["id"])
        beats = []
        for j, b in enumerate(sc.get("beats") or []):
            rec = {k: v for k, v in b.items() if k not in ("t",)}
            t_local, source = b.get("t"), "t"
            if "on" in b:
                try:
                    at = resolve(grid, b["on"], sc["id"])
                    t_local, source = round(at - gsc["start"], 4), "on"
                except GridError as e:
                    if "t" not in b:
                        problems.append(f"scene {sc['id']} beat {j}: {e}")
                        continue
            if t_local is None:
                continue
            rec.update({"t": round(float(t_local), 4), "at": round(gsc["start"] + float(t_local), 4),
                        "source": source})
            beats.append(rec)
        beats.sort(key=lambda r: r["at"])
        out.append({"id": sc["id"], "start": gsc["start"], "duration": gsc["duration"],
                    "beats": beats})
    if problems:
        raise GridError("\n".join(problems))
    return {"scenes": out}


# ---- CLI ------------------------------------------------------------------------------------

def _load(project, name):
    with open(os.path.join(project, name)) as f:
        return json.load(f)


def _dump(project, name, data):
    path = os.path.join(project, name)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    return path


def cmd_build(a):
    sb = _load(a.project, "storyboard.json")

    def words_for(sc):
        w, src, dur = wt.scene_words(a.project, str(sc["id"]), sc.get("narration", ""),
                                     use_asr=not a.no_asr)
        return w, src, dur

    grid = build(sb, words_for, a.lead, a.tail, a.min_scene)
    path = _dump(a.project, "grid.json", grid)
    nw = sum(len(s["words"]) for s in grid["scenes"])
    print(f"-> {path}  {len(grid['scenes'])} scenes, {nw} words, {grid['duration']:.2f}s, "
          f"{len(grid['cues'])} cues")
    for s in grid["scenes"]:
        print(f"   s{s['n']:02d}  {s['start']:7.2f} - {s['end']:7.2f}  ({s['duration']:.2f}s, "
              f"words: {s['words_source']})")
    if a.write_durations:
        for sc, gs in zip(sb["scenes"], grid["scenes"]):
            sc["est_duration_s"] = round(gs["duration"], 1)
        sb["target_duration_s"] = round(grid["duration"])
        _dump(a.project, "storyboard.json", sb)
        print("storyboard est_duration_s / target_duration_s updated from speech")
    return 0


def cmd_resolve(a):
    sb, grid = _load(a.project, "storyboard.json"), _load(a.project, "grid.json")
    try:
        res = resolve_beats(sb, grid)
    except GridError as e:
        print(f"unresolved anchors:\n{e}", file=sys.stderr)
        return 1
    path = _dump(a.project, "beats.resolved.json", res)
    n = sum(len(s["beats"]) for s in res["scenes"])
    on = sum(1 for s in res["scenes"] for b in s["beats"] if b["source"] == "on")
    print(f"-> {path}  {n} beats ({on} anchored to words)")
    return 0


def cmd_cue(a):
    grid = _load(a.project, "grid.json")
    key = a.cue.lower()
    if key in grid["cues"]:
        print(f"{grid['cues'][key]:.4f}")
        return 0
    try:
        print(f"{resolve(grid, a.cue):.4f}")
        return 0
    except GridError as e:
        print(e, file=sys.stderr)
        return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmds = {"build", "resolve", "cue"}
    if not argv or argv[0] not in cmds:
        argv.insert(0, "build")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("project")
    b.add_argument("--lead", type=float, default=DEFAULT_LEAD)
    b.add_argument("--tail", type=float, default=DEFAULT_TAIL)
    b.add_argument("--min-scene", type=float, default=DEFAULT_MIN_SCENE)
    b.add_argument("--no-asr", action="store_true", help="never run forced alignment")
    b.add_argument("--write-durations", action="store_true",
                   help="write the speech-derived durations back into storyboard.json")
    b.set_defaults(fn=cmd_build)
    r = sub.add_parser("resolve")
    r.add_argument("project")
    r.set_defaults(fn=cmd_resolve)
    c = sub.add_parser("cue")
    c.add_argument("project")
    c.add_argument("cue")
    c.set_defaults(fn=cmd_cue)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
