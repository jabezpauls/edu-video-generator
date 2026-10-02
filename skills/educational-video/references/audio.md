# Audio: narration grid, music bed, sound effects, mix

Picture and sound share one clock, the **narration grid**. Narration is produced first; every
scene's length, every animation beat and every sound effect is read from it. All commands run
from the repo root; `<p>` is the project directory. Python scripts that need numpy/scipy or
faster-whisper run fine from the project venv (`<p>/.venv/bin/python`), which `bootstrap.sh`
fills; `mix.py`, `mux.sh` and `sfx.mjs` need only ffmpeg or node.

```
tts.py <p>                     narration per scene   -> audio/scene_<id>.wav (+ .words.json)
grid.py <p> --write-durations  word times, scene slots, cues -> grid.json (storyboard durations updated)
grid.py resolve <p>            beat `on` anchors     -> beats.resolved.json
grid.py cues <p>               sound-effect plan     -> cues.json
sfx.mjs <p>                    sound effects         -> audio/sfx.wav
music.py <p> --mood curious    music bed             -> audio/music.wav
mix.py <p>                     master                -> audio/mix.wav  (-14 LUFS, TP <= -1 dBTP)
align_subtitles.py <p>         captions              -> output/subtitles.srt / .ass
mux.sh <p>                     final video           -> output/final.mp4
```
`mux.sh` runs `mix.py` itself when `mix.wav` is missing or older than its inputs, so after
changing narration, music or sfx you can go straight to `mux.sh`.

## 1. The grid (`grid.json`)

`grid.py` aligns each scene's spoken words to the narration text in the storyboard (provider
timings, else faster-whisper, else an estimate; see `tts-setup.md`) and lays the scenes end to
end on one clock, in seconds.

```jsonc
{ "version": 1, "lead": 0.4, "tail": 0.6, "hit_lead": 0.06, "fps": 30, "duration": 14.02,
  "scenes": [{ "id": "01", "n": 1, "start": 0.0, "end": 7.49, "duration": 7.49,
               "audio": "audio/scene_01.wav", "audio_start": 0.4,
               "speech_start": 0.4, "speech_end": 6.88, "words_source": "asr",
               "words": [{ "i": 0, "word": "Multiplying", "norm": "multiplying",
                           "start": 0.4, "end": 1.06, "phrase": 1 }],
               "phrases": [{ "i": 1, "start": 0.4, "end": 2.9, "text": "Multiplying by i ..." }] }],
  "cues": { "s01.start": 0.0, "s01.w3": 1.78, "s01.rotates": 1.78, "s01.p2": 3.2, "s01.end": 6.88 } }
```

**Scene durations come from speech**: `duration = lead + speech + tail`
(defaults 0.4 s lead-in, 0.6 s tail, minimum 1.5 s; `--lead`, `--tail`, `--min-scene`). The
tail is where the last visual lands before the next scene. `--write-durations` copies the result
into `est_duration_s` / `target_duration_s`, so the storyboard matches what will render. Scenes
without narration keep `est_duration_s`; with no audio yet the speech is estimated from word
length (about 2.6 words per second), which is good enough for blocking and is flagged
`words_source: "estimated"`. Re-run `grid.py` after any narration change.

### Cue names

| Cue | Meaning |
|---|---|
| `s03.start` | start of scene 3's slot (before the lead-in) |
| `s03.end` | end of the speech in scene 3 |
| `s03.w12` | word index 12, zero-based |
| `s03.derivative` | first occurrence of that word (lowercase, punctuation stripped) |
| `s03.derivative#2` | the second occurrence |
| `s03.p2` | start of sentence 2 (one-based); sentences end at `. ! ? ; :` |

`start`, `end`, `wN` and `pN` are reserved. To anchor on the word "end", write `end#1`.
`grid.py cue <p> s01.rotates#2` prints one time; `s3.` and `s03.` both name scene `"03"`.

### Anchors in the storyboard

A beat's `"on": "rotates"` resolves to the word's time; `grid.py resolve` writes
`beats.resolved.json` with, per beat, `t` (seconds from the scene's start) and `at` (global),
and `source` (`on` or `t`). `on` wins over `t` once it resolves; if it cannot (typo, word not
spoken that many times) and there is a `t`, the `t` is used, otherwise `resolve` fails and lists
every unresolved anchor. Choose rare, content words (`derivative`, `ninety`) rather than
`the`; use `#2` when a word repeats.

### Visual lead

The ear notices a visual that is late far more than one that is early. Start every
word-anchored animation `hit_lead` (0.06 s) before its cue so the picture arrives on the word.
Sound effects sit exactly on the cue.

## 2. Sound effects

`grid.py cues` turns resolved beats into `cues.json`:

```json
{ "sr": 48000, "duration": 14.02, "cues": [{ "t": 1.78, "type": "pop", "gain": 0.7, "pitch": 1.0, "pan": -0.1, "what": "pop_in dot" }] }
```
This file is the interface to `sfx.mjs`; any engine's sync step can write the same shape. The motion
engine's `sync.mjs` writes it too (`"source": "timeline"`, from the sfx in `timeline.json`); `grid.py cues`
writes `"source": "grid"`. Neither silently replaces the other: `sync.mjs` keeps a grid plan unless the
timeline declares sfx, and `grid.py cues` needs `--force` to replace a timeline plan.

| Beat action | Sound | Notes |
|---|---|---|
| `pop_in`, `fade_in`, `draw`, `slide_in`, `scale` | `pop` | something appears |
| `write` | `pop`, or `tick` on a code element | typing |
| `highlight`, `indicate` | `click` | emphasis |
| `transform`, `move` | `whoosh` | builds 0.3 s, peaks on the cue |
| scene change | `whoosh` | peaks as the new scene starts |
| `"sfx": "chime"` on a beat | `chime` | the "aha" / result |
| `"sfx": "thump"` on a beat | `thump` | an impact, the answer landing |
| `"sfx": "none"` on a beat | nothing | silence it |

Sounds closer than 90 ms collapse to the louder one. Pitch and pan jitter are seeded, so a
re-run gives the same file. Keep sounds sparse: they punctuate, they are not a soundtrack. A
beat that fires several times a second wants `"sfx": "none"` on all but the first.

## 3. Music bed

`music.py <p> --mood calm|curious|upbeat|none` writes a seeded, quiet bed of pads and a sparse
mallet motif, with a new chord and a soft swell at each scene boundary (the bed follows the
scenes; the visuals follow the words). `--seed N` gives a different take. `none` removes any
existing bed.

| Mood | Feel | Use for |
|---|---|---|
| `calm` | slow warm pad, rare bell | proofs, derivations, reflective |
| `curious` | pad + sparse mallet, light echo | concept explainers (default) |
| `upbeat` | brighter chords, steady mallet, soft pulse | intros, recaps, shorts |

To use your own track instead, convert it (`ffmpeg -i in.mp3 -ar 48000 audio/music.wav`);
`mix.py` trims and levels it like the synthesized bed.

## 4. Mix and master

`mix.py <p>` places each scene's narration at its `audio_start` on the grid clock
(`audio/vo.wav`), levels the stems against the narration, ducks the bed under the voice, and
masters to **-14 LUFS integrated with true peak at or below -1 dBTP** (48 kHz, 24-bit).

- **Levels** are in dB relative to the narration: music `-17` (before ducking), sfx `-9`, vo `0`.
  Override per project in `<p>/mix.json` (`{"music": -20, "sfx": -8, "duck_db": 6}`) or per run
  with `--music`, `--sfx`, `--vo`, `--target`.
- **Ducking** is a side-chain compressor keyed by the narration: about 8 dB under speech (`duck_db`),
  20 ms attack, 350 ms release so the bed breathes back in between phrases. `--no-duck` disables it.
- **Mastering** applies a linear gain to the target and a 4x-oversampled limiter, then re-measures
  and corrects, because synthesized transients cause inter-sample overs a plain limiter misses.
- **Report**: `audio/mix_report.json` has the measured loudness and true peak; `--stems` also
  writes the levelled, ducked stems to `audio/stems/` for inspection.
- A `WARNING: off target` (exit code 2) means the limiter is working too hard; lower the
  loudest stem, usually sfx, and re-run.

Loudness is measured on the final MP4 as well (`ffmpeg -i output/final.mp4 -af ebur128=peak=true -f null -`);
AAC encoding at 256 kbit/s moves it by less than 0.1 LU.

## 5. Muxing

`mux.sh <p>` conforms each `output/scene_<id>.mp4` to its grid slot (holds the last frame if the
render is short, trims if long, and warns beyond 0.25 s / 0.1 s: fix the animation instead of
relying on it), concatenates the scenes, and muxes `audio/mix.wav`. Subtitles are soft (`mov_text`)
by default, `--burn` hardcodes `subtitles.ass`. Do not add audio inside Manim or Remotion scenes:
the mix is the only audio track, so loudness is guaranteed.

Engines read the grid with `scenes/gridsync.py` (Manim) and `scenes/src/gridsync.ts` (Remotion), copied from `templates/`;
see `manim-patterns.md` and `remotion-patterns.md`.

Formats: `mux.sh <p> --format all` assembles every format of the storyboard (`final.mp4` is the first,
`final_<fmt>.mp4` the others); 9x16 always gets `subtitles_9x16.ass` burned in, the rest a soft track. The scene
videos it reads are `scene_<id>.<fmt>.mp4` (`render.sh <engine> <p> all <q> all`).

Motion lessons need no mux step: they are one film, so `render.sh motion <p> all high` writes
`output/final*.mp4` with `audio/mix.wav` (and the soft `output/subtitles.srt` for non-9x16 formats) already in
them. `render.mjs --mux` re-attaches a new mix to existing renders without re-rendering the picture. Cue names
(`s03.three`) are the same in the film, in `grid.json` and in the storyboard's `on` anchors.

Presets feed this chain: the voice (`tts.py`), the music mood and level (`music.py`, `mix.py`) and whether
sound effects are on (`mix.py`) come from the applied preset (`preset.json`) when you do not say otherwise.
Apply the preset before narration. A short defaults to the `upbeat` bed.

## 6. Checking sync

Pick three anchored beats and compare the frame where the visual starts with the cue time:
extract frames around `grid.py cue <p> s01.ninety` (`ffmpeg -ss <t> -i output/final.mp4 -frames:v 1`).
The visual should begin within 80 ms before the cue and never after it.
