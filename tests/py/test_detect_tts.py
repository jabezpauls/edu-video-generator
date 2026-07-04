import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS


def detect(env_extra, tmp_path):
    # Minimal environment: no keys, and a PATH that cannot find piper or espeak-ng.
    env = {"PATH": str(tmp_path), **env_extra}
    r = subprocess.run([sys.executable, str(SCRIPTS / "detect_tts.py"), str(tmp_path)],
                       capture_output=True, text=True, env=env, check=True)
    return json.loads(r.stdout)


def test_nothing_available(tmp_path):
    d = detect({}, tmp_path)
    assert d["provider"] == "none"


def test_elevenlabs_has_priority(tmp_path):
    d = detect({"ELEVENLABS_API_KEY": "k", "OPENAI_API_KEY": "k"}, tmp_path)
    assert d["provider"] == "elevenlabs" and d["word_timestamps"] is True


def test_openai_when_only_openai(tmp_path):
    assert detect({"OPENAI_API_KEY": "k"}, tmp_path)["provider"] == "openai"


@pytest.mark.parametrize("exe, provider", [("piper", "piper"), ("espeak-ng", "espeak-ng")])
def test_local_engines_found_on_path(tmp_path, exe, provider):
    bin_ = tmp_path / exe
    bin_.write_text("#!/bin/sh\n")
    bin_.chmod(0o755)
    assert detect({}, tmp_path)["provider"] == provider
