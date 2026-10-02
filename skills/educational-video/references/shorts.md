# Shorts

A short is a 30-60 second vertical micro-lesson for phones: one hook, one idea, one payoff. It is
a storyboard with `"mode": "short"`; everything else in the pipeline is the same, with these
defaults.

| | lesson | short |
|---|---|---|
| duration | whatever the topic needs | 30-60 s (`target_duration_s`, validated) |
| formats | `["16x9"]` | `["9x16"]` |
| engine | scored by content | **motion**, unless the user chose another |
| captions | soft subtitles (16x9, 1x1, 4x5) | burned in, word by word |
| music bed | preset mood, else `curious` | preset mood, else `upbeat` |
| critic thresholds | lesson | short (`review.py --mode short`, picked from the storyboard) |

Start one with `scripts/new_project.sh <base> <slug> --short`: it writes `mode`, `formats` and
`engine` into the manifest, scaffolds the motion engine and seeds `storyboard.json` from
`templates/short.storyboard.json` (hook, idea, example, payoff, recap).

## Shape

1. **Hook, at most 3 seconds.** A question or a claim, not a title card. Seven words or fewer
   (2.6 words a second). Frame 0 already shows something, and the validator requires a beat
   at `t <= 1` (or an `on` anchor) in scene 1. The hook scene itself stays under 5 s.
2. **The idea.** One sentence, in plain words. If you need two, it is two shorts.
3. **Show it.** One concrete example, one step per sentence, each step a visual event
   (about every 2-4 s; shorts are faster than lessons). One equation, one diagram or one
   snippet of code on screen at a time.
4. **Payoff.** What the learner can now do or see, with a `thump` or `chime` on the result.
5. **Recap**, six words or fewer, restating the idea. No "like and subscribe".

Five to eight scenes. More than eight is more than one idea (the validator warns).

## Writing for the ear and the thumb

- Short sentences. Numbers as words ("sixteen"). No LaTeX in `narration`.
- Put the content word you want to land on the picture in the narration and anchor the beat to
  it: `{"on": "sixteen", "action": "pop_in"}`. Captions are burned in, so every spoken word is
  also read: the visual has to add something to the words.
- Text at least 64 px on a 1080-wide frame (about 6 % of the width). The motion components pick
  phone sizes with `C.pick(wide, square, tall)`; write the tall number first in your head.
- Keep clear of the platform UI: top 14 %, bottom 20 %, right 12 %. The captions sit just above
  the bottom zone, so lay content out in `EDU.zone(...)` boxes, which already leave that strip.
- Nothing may sit still for long: the short thresholds in `review.py` warn at 3 s without movement and fail at 5 s.

## Captions

The motion engine adds burned-in captions on its own: when the narration grid exists and the
render is `9x16`, `C.start()` adds a caption overlay built from `C.GRID.words` (sync.mjs puts the
words there). Nothing to write in `film.js`. A preset's `captions` block (style `pill`, `plain`
or `outline`, accent or highlight for the spoken word) restyles them. Manim and Remotion shorts
are captioned by `mux.sh`, which burns `output/subtitles_9x16.ass` (made by `align_subtitles.py`,
type at 68 px, kept inside the safe zones).

## Deriving a short from a lesson

Do not re-cut the lesson; re-write one idea from it.

1. Pick the single most surprising or most useful moment of the lesson (the "aha").
2. Write the hook as the question that moment answers.
3. Copy that scene's visual (same equation, same diagram) as the "show it" scene; drop the
   derivation that led to it.
4. Write a new 30-60 s script (the lesson's narration is too slow and too long to reuse), a new
   `short.storyboard.json`, same `preset` as the lesson so the two look related.
5. If the lesson is a motion project, `cp` its `film/film.js` scenes as a starting point and
   re-block them with `C.pick`; the components are the same. Otherwise start fresh with
   `new_project.sh --short`.

To get a 9:16 version of the **whole lesson** instead, add `"9x16"` to its `formats`: every
motion scene is re-blocked per format, Manim and Remotion render one composition per format.
See `formats.md`.

## Checklist before the critic

- First 3 seconds: a question or claim on screen at frame 0, spoken by 3 s.
- Duration 30-60 s; `render.sh ... all` and `review.py` agree on it.
- Captions: look at the phone sheet; they never cover the thing being explained, and the
  spoken word is highlighted.
- Loudness -14 LUFS (`audio/mix_report.json`); the bed is audible but never competes.
- The recap says the idea in the same words as the hook asked it.
