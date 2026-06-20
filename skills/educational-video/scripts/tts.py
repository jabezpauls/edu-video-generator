#!/usr/bin/env python3
"""Synthesize per-scene narration audio using the resolved provider.

Reads <project>/.videogen/env.json for the provider, <project>/storyboard.json for
each scene's narration text. Writes audio/scene_<id>.wav and, when the provider
supports it, audio/scene_<id>.words.json (word timestamps).

Usage: tts.py <project-dir>
Providers: elevenlabs | openai | piper | espeak-ng
"""
import json
import os
import subprocess
import sys


def load(project):
    env = {}
    ep = os.path.join(project, ".videogen", "env.json")
    if os.path.isfile(ep):
        env = json.load(open(ep)).get("tts", {}) or {}
    sb = json.load(open(os.path.join(project, "storyboard.json")))
    return env, sb


def synth_espeak(text, out_wav):
    subprocess.run(["espeak-ng", "-w", out_wav, text], check=True)


def synth_piper(text, out_wav, binp, model):
    with subprocess.Popen([binp, "--model", model, "--output_file", out_wav],
                          stdin=subprocess.PIPE) as p:
        p.communicate(text.encode())
        if p.returncode:
            raise RuntimeError("piper failed")


def synth_openai(text, out_wav):
    from openai import OpenAI
    client = OpenAI()
    # stream to an mp3 then let mux/ffmpeg handle it; save as .mp3 sibling
    mp3 = out_wav.rsplit(".", 1)[0] + ".mp3"
    with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice="alloy", input=text) as resp:
        resp.stream_to_file(mp3)
    subprocess.run(["ffmpeg", "-y", "-i", mp3, out_wav],
                   check=True, capture_output=True)


def synth_elevenlabs(text, out_wav, model):
    import urllib.request
    key = os.environ["ELEVENLABS_API_KEY"]
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    body = json.dumps({"text": text, "model_id": model}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "xi-api-key": key, "Content-Type": "application/json",
        "Accept": "audio/mpeg"})
    mp3 = out_wav.rsplit(".", 1)[0] + ".mp3"
    with urllib.request.urlopen(req) as r, open(mp3, "wb") as f:
        f.write(r.read())
    subprocess.run(["ffmpeg", "-y", "-i", mp3, out_wav],
                   check=True, capture_output=True)


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    env, sb = load(project)
    if not sb.get("narration", True):
        print("narration disabled in storyboard; skipping TTS")
        return 0
    provider = env.get("provider", "none")
    audio_dir = os.path.join(project, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    if provider == "none":
        print("ERROR: no TTS provider available (run bootstrap)", file=sys.stderr)
        return 1

    for sc in sb["scenes"]:
        text = (sc.get("narration") or "").strip()
        if not text:
            continue
        out = os.path.join(audio_dir, f"scene_{sc['id']}.wav")
        try:
            if provider == "elevenlabs":
                synth_elevenlabs(text, out, env.get("model", "eleven_multilingual_v2"))
            elif provider == "openai":
                synth_openai(text, out)
            elif provider == "piper":
                synth_piper(text, out, env.get("bin", "piper"),
                            os.path.join(project, "assets", "tts",
                                         env.get("model", "en_US-amy-medium") + ".onnx"))
            elif provider == "espeak-ng":
                synth_espeak(text, out)
            else:
                print(f"unknown provider {provider}", file=sys.stderr)
                return 1
            print(f"-> {out}")
        except Exception as e:  # noqa: BLE001
            print(f"TTS failed for scene {sc['id']}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
