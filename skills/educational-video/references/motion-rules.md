# Motion rules (lessons)

House rules for every motion-engine lesson. They keep renders deterministic and the motion consistent; they apply
even when the user's brief says nothing about them. A project's own notes win where they are stricter. Where a
rule needs the API, see `motion-engine.md`.

## Render contract

- The lesson is a pure function of time. `window.seek(t)` paints frame `t`, in any order, cold or after any other frame.
- No CSS transitions or animations, no `setTimeout`, no `requestAnimationFrame`, no `Date`, and no state carried
  between frames (no variable mutated in `run()`).
- Randomness is seeded only (`C.mulberry32(seed)`, `C.noise1(seed)`). Never `Math.random`.
- No `will-change`, no `translate3d`, no `translateZ(0)`. A composited layer caches its raster, so the same `t` paints
  differently depending on the previous frame. Use 2D transforms (`C.put` does). If a shot truly needs CSS 3D, run
  `--verify` on it and fall back to skew + scale + shadow if it fails.
- Output is H.264 yuv420p with bt709 tags; finals are 60 fps, CRF 16. Drafts are 30 fps.
- Run `scripts/render.sh motion <project> all verify` once per lesson, and again after anything structural changes.

## Springs only

- Everything that enters, exits or retargets rides a closed-form spring from `lib/motion.js`. No easing curves.
  Linear progress (`C.seg`) is for typing, scrolls and slow pushes only.
- A value with more than one target uses `C.trk()`: one spring per change, each starting at its own time, so a retarget
  keeps its velocity. Never restart a spring.
- Presets: `heavy` for titles and big type, `default` for cards, diagrams, panels and the camera, `snappy` for pointers,
  highlights, selections and pops, `playful` for characters only (never notation, labels or type).
- Visual hits that sit on a spoken word or a sound use `C.spHit` so they read on the cue; `C.sp` is for silent motion.
- Text inside a morphing box enters after the morph starts and leaves before the next one (`Motion.swapAlpha`).

## Enters, exits and swaps

- **Enters:** rise through a mask, grow out of something (scale 0.8-0.9 to 1, opacity snapping on within 4 frames), type
  on, draw on, build skeleton to content, card rise.
- **Exits:** lift through the mask, get covered, push past the camera, collapse into what replaces it, a hard cut. Content
  the explanation has moved past recedes (dims) rather than vanishing, unless it would confuse.
- A pure opacity fade is never the enter or exit of a primary element (a term, a line of code, a node, a title). Small
  eyebrow and caption-support lines may fade.
- **Swaps are sequential.** The outgoing line is gone before the incoming one lands (`rise(t, L, in, nextIn - 0.05)`).
  At most one frame of overlap, with the outgoing line at least 95 % gone.
- Masked words start at least 140 % of their size below the mask so no glyph tops show on the first frame.
- Every scene's elements are animated on every frame they are registered; anything registered visible leaks outside its window.

## Look

- **Banned defaults:** centred title on a gradient, everything fading in, corner labels and frame borders, glow on UI chrome,
  generic particle bursts, crossfades between scenes, spins, glitches, light leaks, bouncy easing on anything that is read.
- One display face and one body face (a monospace for code). System fonts are fine for drafts.
- One accent colour for "the thing this scene is about", plus one **highlight hue** (`--hi`) reserved for emphasis inside
  a derivation, a code line or a diagram (the active term, the current pointer). Never use more than these two plus ink.
- **Real notation, real code, real data.** Never paraphrase an equation, retype a code sample from memory or round a number
  for looks: use the exact string from the storyboard. A diagram that claims to show an algorithm shows its actual values.
- Type is left-aligned at x >= 120 px on 1080p (70-90 px in tall frames) and in sentence case; the accent goes on the key
  word only.
- Anything that must be read is at least 28 px on 1080p and still legible in the 360 px phone sheet. Scale the layout,
  not the font.
- 9:16 keeps key content out of the platform zones: top 14 %, bottom 20 %, right 12 %.
- Re-block per format with `C.pick(wide, square, tall)` and `C.H > C.W`; never letterbox a 16:9 composition into a tall frame.

## Rhythm (relaxed for teaching)

- A new visual event every 3-6 seconds. Nothing holds longer than about 8 seconds without something changing.
- A longer hold is fine **while the narration explains a displayed result** (a finished equation, a final array, a plot),
  as long as it carries a micro push (scale 1.00 to 1.03-1.06) or a slow drift. A frozen frame is never acceptable.
- One idea at a time: reveal a term or a step when it is spoken about, not before. Signal what to look at (highlight,
  pointer, dim the rest) instead of adding more on screen.
- The hook reads in the first 3 seconds and frame 0 is never empty. The last scene holds no longer than 3 seconds.
- Place things on cues or marks (`'s02.derivative'`, `'idea+0.3'`), not on hard-coded seconds, once narration exists.
  Until then marks in `timeline.json` are the timing; the narration phase re-points them at cues.

## Process

- Loop before showing anything: contact sheet, look at it, fix the worst problems, repeat. Judge rendered frames and
  sheets, never memory of the code.
- Use a distinctive project folder name, never write into a folder you did not create, and if files change underneath
  you, stop and check.
