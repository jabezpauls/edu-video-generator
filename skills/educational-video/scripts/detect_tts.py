#!/usr/bin/env python3
"""Resolve the TTS provider for this run and print a capability descriptor as JSON.

Detection order: ELEVENLABS_API_KEY -> OPENAI_API_KEY -> local Piper -> espeak-ng.
Usage: detect_tts.py [project-dir]
"""
import json
import os
import shutil
import sys


def find_piper(project: str | None) -> str | None:
    # explicit project-local install first
    if project:
        cand = os.path.join(project, "assets", "tts", "piper")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return shutil.which("piper")


def main() -> int:
    project = sys.argv[1] if len(sys.argv) > 1 else None

    if os.environ.get("ELEVENLABS_API_KEY"):
        desc = {"provider": "elevenlabs", "model": "eleven_multilingual_v2",
                "word_timestamps": True}
    elif os.environ.get("OPENAI_API_KEY"):
        desc = {"provider": "openai", "model": "gpt-4o-mini-tts",
                "word_timestamps": False}
    elif find_piper(project):
        desc = {"provider": "piper", "model": "en_US-amy-medium",
                "word_timestamps": False, "bin": find_piper(project)}
    elif shutil.which("espeak-ng"):
        desc = {"provider": "espeak-ng", "model": "default",
                "word_timestamps": False}
    else:
        desc = {"provider": "none", "model": None, "word_timestamps": False,
                "note": "no TTS available; bootstrap should install piper"}

    print(json.dumps(desc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
