"""Project settings the audio scripts share: the applied preset (preset.json) and the storyboard mode."""
import json
import os


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def preset(project):
    """The resolved preset apply_preset.py wrote into the project, or {}."""
    p = read_json(os.path.join(project, "preset.json"), {})
    return p if isinstance(p, dict) else {}


def mode(project):
    sb = read_json(os.path.join(project, "storyboard.json"), {})
    m = sb.get("mode") if isinstance(sb, dict) else None
    return m if m in ("lesson", "short") else "lesson"


def music_mood(project, explicit=None):
    """--mood wins, then the preset's, then upbeat for a short, else curious."""
    if explicit:
        return explicit
    return preset(project).get("music", {}).get("mood") or ("upbeat" if mode(project) == "short" else "curious")
