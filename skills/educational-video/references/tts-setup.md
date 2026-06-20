# TTS setup & narration

Narration provider is resolved **per run** by `scripts/detect_tts.py` and cached in
`.videogen/env.json`. Higher-quality cloud providers are used when a key is present; otherwise a
local offline engine.

## Detection order

1. `ELEVENLABS_API_KEY` → ElevenLabs (best quality, word timestamps available).
2. `OPENAI_API_KEY` → OpenAI TTS (`gpt-4o-mini-tts` / `tts-1`; no per-word timestamps → forced
   alignment in Phase 8).
3. Local **Piper** (offline, free; no word timestamps → forced alignment).
4. `espeak-ng` (last-resort intelligibility fallback).

`detect_tts.py` prints a capability descriptor:
```json
{ "provider":"piper", "model":"en_US-amy-medium", "word_timestamps": false }
```

> On this machine no cloud key is set, so the default is **Piper** with whisper-based forced
> alignment for subtitles. To get higher-quality narration, set `ELEVENLABS_API_KEY` or
> `OPENAI_API_KEY` in the environment and re-run; mention this option to the user on first run.

## Call recipes (used by `scripts/tts.py`)

**ElevenLabs** (REST): POST text → audio; request character/word timestamps endpoint when
available; save `audio/scene_<id>.wav` + `audio/scene_<id>.words.json`.

**OpenAI**: `client.audio.speech.create(model="gpt-4o-mini-tts", voice="alloy", input=text)` →
save audio; no word timings (align in Phase 8).

**Piper** (offline):
```bash
echo "narration text" | ./assets/tts/piper --model assets/tts/en_US-amy-medium.onnx \
  --output_file audio/scene_01.wav
```

**espeak-ng**: `espeak-ng -w audio/scene_01.wav "text"` (robotic; fallback only).

## Word timestamps

- If the provider returns word timings, write them to `audio/scene_<id>.words.json` as
  `[{"word":"Let","start":0.0,"end":0.18}, ...]`.
- Otherwise leave it absent; Phase 8 runs forced alignment.

## Forced alignment (Phase 8 fallback)

Installed lazily only when needed:
```bash
uv pip install faster-whisper
```
Transcribe the synthesized audio with word timestamps and emit them — produces accurate captions
even when the TTS engine doesn't expose timings. (`aeneas` is an alternative if a reference
transcript is preferred over ASR.)

## Voice & language

- Respect `storyboard.language` and any user voice preference.
- Keep narration text speakable: expand math/symbols ("e to the i pi equals minus one"), spell
  out abbreviations where natural.
