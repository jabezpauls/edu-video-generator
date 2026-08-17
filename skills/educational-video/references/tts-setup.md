# TTS setup & narration

Narration provider is resolved **per run** by `scripts/detect_tts.py` and cached in
`.videogen/env.json`. Cloud providers are used when a key is present; otherwise a local offline
engine. Narration is produced **before** the scenes are coded: its timings become the
narration grid (`audio.md`), which fixes scene lengths and beat times.

## Detection order

1. `ELEVENLABS_API_KEY` -> ElevenLabs (best quality, character timestamps -> word times).
2. `OPENAI_API_KEY` -> OpenAI TTS (`gpt-4o-mini-tts`; no timestamps -> forced alignment).
3. Local **Piper** (offline, free; no timestamps -> forced alignment). `bootstrap.sh` installs it
   into the project venv (`.venv/bin/piper`) with the `en_US-amy-medium` voice under
   `assets/tts/` when no cloud key is set. `PIPER_VOICE=en_GB-alan-medium bootstrap.sh ...`
   picks another voice (any name from the Piper voice list).
4. `espeak-ng` (last-resort intelligibility fallback).

`detect_tts.py` prints a capability descriptor:
```json
{ "provider": "piper", "model": "en_US-amy-medium", "word_timestamps": false, "bin": "/abs/.venv/bin/piper" }
```
Without a cloud key the default is Piper; mention `ELEVENLABS_API_KEY` / `OPENAI_API_KEY` to
the user as the way to get better narration, then re-run `tts.py`.

## Running it

```bash
python3 scripts/tts.py <project>            # synthesize every narrated scene
python3 scripts/tts.py <project> --force    # redo all scenes
python3 scripts/tts.py <project> --provider piper
```
One file per scene: `audio/scene_<id>.wav` (+ `audio/scene_<id>.words.json` when the provider
returns timings). `audio/tts_cache.json` remembers a hash of provider, voice and text, so only
scenes whose narration changed are re-synthesized. Stale timings are deleted when a scene is
redone. `tts.py` warns when narration contains symbols a voice would mangle (`$`, `\`, `^`,
`3/4`): write them as words.

Voice selection: `ELEVENLABS_VOICE_ID`, `OPENAI_TTS_VOICE`, or `"voice"` in the `tts` object of
`.videogen/env.json`. Respect `storyboard.language` and any voice the user asked for.

## Word timings

`grid.py` needs the time of every spoken word. It gets them, in order of preference:

1. **Provider timings**, `audio/scene_<id>.words.json` as
   `[{"word":"Let","start":0.0,"end":0.18}, ...]` (ElevenLabs).
2. **Forced alignment** with faster-whisper (the `base` model, CPU, int8) on the scene wav,
   cached back into `scene_<id>.words.json`. `bootstrap.sh` installs it with Piper; it is
   installed lazily otherwise. The first run downloads the model (about 140 MB).
3. **Estimate** from word lengths if neither is available, flagged `words_source: "estimated"`.

Whichever source is used, the words are then snapped onto the narration text from the
storyboard, so a recognizer mishearing "e to the i pi" never breaks an anchor: heard words are
matched to the written ones in order and the rest are interpolated. Check the report:
`grid.py` prints the word source per scene. Prefer a re-run with `--no-asr` only to skip alignment
deliberately.

## Writing narration that works

- Keep it speakable: expand math and symbols ("e to the i pi equals minus one"), spell out
  abbreviations where natural. Raw LaTeX in narration is a validator warning for a reason.
- One idea per sentence: sentences become phrases (`s03.p2`) that animations can anchor to.
- Put the word you want to anchor on early and make it distinctive.
- Short scenes (3-12 s) are easier to keep in sync than one long scene.
