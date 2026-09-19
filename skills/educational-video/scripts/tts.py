#!/usr/bin/env python3
"""Synthesize per-scene narration audio using the resolved provider.

Reads <project>/.videogen/env.json for the provider, <project>/storyboard.json for
each scene's narration text. Writes audio/scene_<id>.wav and, when the provider
supports it, audio/scene_<id>.words.json (word timestamps). Providers without timings are
aligned later by grid.py (faster-whisper), so run grid.py after this.

Scenes whose narration text, provider and voice are unchanged since the last run are skipped.

Usage: tts.py <project-dir> [--force] [--provider NAME]
Providers: elevenlabs | openai | piper | espeak-ng
Voice: "voice" in .videogen/env.json, else ELEVENLABS_VOICE_ID / OPENAI_TTS_VOICE, else the applied preset's
voice for the provider (preset.json), else the provider default. A Piper voice the preset names but that is not
downloaded into assets/tts/ is skipped with a warning.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import projectcfg  # noqa: E402


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


def synth_openai(text, out_wav, voice="alloy"):
    from openai import OpenAI
    client = OpenAI()
    # stream to an mp3 then let mux/ffmpeg handle it; save as .mp3 sibling
    mp3 = out_wav.rsplit(".", 1)[0] + ".mp3"
    with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice=voice, input=text) as resp:
        resp.stream_to_file(mp3)
    subprocess.run(["ffmpeg", "-y", "-i", mp3, out_wav],
                   check=True, capture_output=True)


def words_from_chars(chars, starts, ends):
    """Collapse ElevenLabs character alignment into [{"word","start","end"}]."""
    words, cur, t0, t1 = [], "", None, None
    for ch, st, en in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": t0, "end": t1})
            cur, t0, t1 = "", None, None
            continue
        if not cur:
            t0 = st
        cur += ch
        t1 = en
    if cur:
        words.append({"word": cur, "start": t0, "end": t1})
    return words


def synth_elevenlabs(text, out_wav, model, voice=None):
    """Synthesize with character timestamps. Returns word timings."""
    import urllib.request
    key = os.environ["ELEVENLABS_API_KEY"]
    voice = voice or os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"
    body = json.dumps({"text": text, "model_id": model}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    mp3 = out_wav.rsplit(".", 1)[0] + ".mp3"
    with open(mp3, "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    subprocess.run(["ffmpeg", "-y", "-i", mp3, out_wav],
                   check=True, capture_output=True)
    al = data.get("alignment") or data.get("normalized_alignment") or {}
    return words_from_chars(al.get("characters", []),
                            al.get("character_start_times_seconds", []),
                            al.get("character_end_times_seconds", []))


def text_hash(provider, model, voice, text):
    return hashlib.sha1(f"{provider}|{model}|{voice}|{text}".encode()).hexdigest()[:16]


def speakable_warnings(sid, text):
    """Narration is read aloud, so raw markup and math symbols are almost always a mistake."""
    if re.search(r"[\\$^_{}]|\d\s*[=+*/]\s*\d", text):
        return [f"scene {sid}: narration contains math/markup symbols; "
                "write them as words (\"e to the i pi\")"]
    return []


def main():
    args = [a for a in sys.argv[1:]]
    force = "--force" in args
    override = None
    if "--provider" in args:
        i = args.index("--provider")
        override = args[i + 1]
        del args[i:i + 2]
    args = [a for a in args if a != "--force"]
    project = args[0] if args else "."
    env, sb = load(project)
    if not sb.get("narration", True):
        print("narration disabled in storyboard; skipping TTS")
        return 0
    provider = override or env.get("provider", "none")
    audio_dir = os.path.join(project, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    if provider == "none":
        print("ERROR: no TTS provider available (run bootstrap)", file=sys.stderr)
        return 1

    model = env.get("model") or None
    voice = env.get("voice") or None
    preset_voice = (projectcfg.preset(project).get("voice") or {}).get(provider) or None
    if provider == "elevenlabs":
        model = model or "eleven_multilingual_v2"
        voice = voice or os.environ.get("ELEVENLABS_VOICE_ID") or preset_voice or "21m00Tcm4TlvDq8ikWAM"
    elif provider == "openai":
        voice = voice or os.environ.get("OPENAI_TTS_VOICE") or preset_voice or "alloy"
    elif provider == "piper":
        if preset_voice and not os.path.isfile(os.path.join(project, "assets", "tts", preset_voice + ".onnx")):
            print(f"warning: the preset's Piper voice {preset_voice} is not in assets/tts/ "
                  f"(python -m piper.download_voices --download-dir assets/tts {preset_voice}); using {model or 'the default'}",
                  file=sys.stderr)
            preset_voice = None
        model = (preset_voice if not env.get("model") else None) or model or "en_US-amy-medium"

    cache_path = os.path.join(audio_dir, "tts_cache.json")
    cache = json.load(open(cache_path)) if os.path.isfile(cache_path) else {}

    for sc in sb["scenes"]:
        sid = sc["id"]
        text = (sc.get("narration") or "").strip()
        if not text:
            continue
        for w in speakable_warnings(sid, text):
            print(f"warning: {w}", file=sys.stderr)
        out = os.path.join(audio_dir, f"scene_{sid}.wav")
        words_path = os.path.join(audio_dir, f"scene_{sid}.words.json")
        digest = text_hash(provider, model, voice, text)
        if not force and os.path.isfile(out) and cache.get(sid) == digest:
            print(f"== {out} (unchanged)")
            continue
        if os.path.isfile(words_path):
            os.remove(words_path)  # stale timings from the previous take
        try:
            words = None
            if provider == "elevenlabs":
                words = synth_elevenlabs(text, out, model, voice)
            elif provider == "openai":
                synth_openai(text, out, voice or "alloy")
            elif provider == "piper":
                synth_piper(text, out, env.get("bin", "piper"),
                            os.path.join(project, "assets", "tts", model + ".onnx"))
            elif provider == "espeak-ng":
                synth_espeak(text, out)
            else:
                print(f"unknown provider {provider}", file=sys.stderr)
                return 1
            if words:
                with open(words_path, "w") as f:
                    json.dump(words, f)
            cache[sid] = digest
            print(f"-> {out}" + (f" (+{len(words)} word times)" if words else ""))
        except Exception as e:  # noqa: BLE001
            print(f"TTS failed for scene {sid}: {e}", file=sys.stderr)
            return 1
        finally:
            with open(cache_path, "w") as f:
                json.dump(cache, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
