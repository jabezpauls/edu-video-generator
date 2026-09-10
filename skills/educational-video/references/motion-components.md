# Motion lesson components

The motion engine ships five components for teaching, in `film/edu/` (copied by `scaffold_motion.sh`, refreshed by
`--update`) and exposed on `window.EDU`. They follow the engine's contract: build DOM once in a scene's `build()`, call
`component.run(t)` from the scene's `run()` every frame, keep nothing between frames. Timing arguments are whens (seconds,
marks, cues; see `motion-engine.md`). Everything re-blocks with `C.pick(wide, square, tall)`.

| Component | For | Entry point |
|---|---|---|
| Equation | derivations, formulas | `EDU.equation(parent, opts)` |
| Code | source listings | `EDU.code(parent, opts)` |
| Plot | functions, line and bar charts | `EDU.plot(parent, opts)` |
| Diagram | arrays, trees, graphs, pointers | `EDU.diagram`, `.array`, `.tree` |
| Captions | burned-in, word-synced | `EDU.captions(parent, opts)` / `.overlay(opts)` |

Look tokens: `ink`, `ink2`, `accent` (the answer, the thing the scene is about) and `hi` (the highlight hue: the active
term, the line being read, the pointer). Components use only those, so a preset restyles them. Syntax colours are
`--c-kw --c-str --c-num --c-com --c-fn --c-op` in `edu/edu.css`.

## Equation

KaTeX 0.19 is vendored under `film/vendor/katex/` (woff2 fonts only), so nothing is fetched and renders work offline.

```js
S.eq = EDU.equation(root, {
  x: 140, y: 400, w: 1640, size: C.pick(170, 130, 150), align: 'left',          // w: the line is scaled down to fit it
  steps: [
    { tex: '\\term{pow}{2^{k}} \\term{eq}{=} \\term{n}{n}', at: 'eq1', reveal: { pow: 'eq1', n: 'eq1_n' } },
    { tex: '\\term{k}{k} \\term{eq}{=} \\term{log}{\\log_2} \\term{n}{n}', at: 'eq2' },
  ],
  hi: [{ term: 'n', from: 'hl', to: 'done', tone: 'hi' }],                      // tone: hi | accent
});
// run(t):  S.eq.run(t);
```

- `\term{id}{tex}` names a piece (letters, digits, `-`, `_`). The tex is the real TeX from the storyboard, nothing is generated.
- Inside a step, pieces enter in reading order, `stagger` apart (default 0.07 s), or on `reveal[id]`. Glue outside any
  `\term` (`=`, `+`, brackets) enters with the next term.
- Between steps, a piece whose id **and typeset result** match glides to its new place; everything else leaves and the new
  pieces enter 0.2 s later, so old and new never overlap. Same id with different tex counts as a new piece.
- `hi` windows tint a term with a spring fill and a small pop. The highlight follows the term through the swap.
- Options: `preset` (enter spring, default `snappy`), `swap` (glide spring, default `default`), `until` (when the last step
  leaves), `fit: false` (do not scale a too-wide step down), `color`.
- A `\term` inside a fraction or root animates by itself, but the bar and root sign belong to the step and show with it.
  Wrap the whole fraction in a `\term` when they should arrive together.
- Narration never contains LaTeX; the storyboard's `narration` is separate from the `tex`.

## Code

```js
S.k = EDU.code(root, {
  x: 120, y: 330, w: 1000, size: 42, lang: 'python', numbers: true, code: SOURCE,       // SOURCE: the exact string from the storyboard
  reveal: { mode: 'type', from: 'code_in', to: 'code_done' },           // or { mode: 'lines', from: 'x', every: 0.35 | at: [whens] }; omit for static
  focus: [{ at: 'cf1', lines: [3, 4] }, { at: 'cf2', lines: [5, 5] }, { at: 'cf3', lines: null }],   // 1-based, inclusive
});
```

Languages: `python`, `javascript` (+ `ts`, `jsx`), `c` (also java, cpp, go, rust), `bash`, `json`, `sql`, `text`. Tokens are
colour-coded with no dependency (`lib/tokens.js`); unknown languages render as plain text.

- Typing counts every character (a newline is one keystroke) over `reveal.from..to`, with a caret that blinks once typing
  is done. Line reveal pops each line in on a spring.
- `focus` moves a band between ranges (the leading edge is stiffer, so it stretches and settles) and dims everything else
  to 28 %. A `null` range clears the focus. Dimming is springs too, so retargets keep their velocity.
- If the longest line does not fit `w` at `size`, the size shrinks until it does (`k.size` is what was used). Phone frames
  have about 30 columns at a readable size: give tall frames a narrower variant of the same code (rename, split a comment
  onto its own line) instead of letting it shrink.

## Plot

```js
S.p = EDU.plot(root, {
  x: 140, y: 100, w: 1500, h: 700, xr: [0, 16], yr: [0, 5], xLabel: 'n', yLabel: 'looks', size: C.pick(36, 38, 42),
  axes: { at: 'axes' },
  curves: [{ fn: (n) => Math.log2(n), from: 1, at: 'curve', dur: 1.8, color: 'accent', label: 'log₂ n' }],
  points: [{ x: 8, y: 3, at: 'pt', label: '8 items: 3 looks', color: 'hi', align: 'right' }],
  segments: [{ from: [8, 0], to: [8, 3], at: 'pt', dash: [10, 10], color: 'hi' }],     // guides, secants, tangents
  markers: [{ curve: 0, stops: [['m1', 4], ['m2', 16]], drop: true, label: (x, y) => `n=${x}: ${y} looks` }],
});
```

- Axes grow from the origin (axes cross at zero when it is in view), then the grid and tick labels settle in.
- A curve is sampled once per frame and truncated to the fraction drawn (a critically damped spring that finishes in about
  `dur` seconds), so the pen travels at constant speed along it. Asymptotes break the line instead of drawing across them.
- `markers` ride a curve between `stops` (`[when, x]`, retargets keep velocity) with optional drop lines and a readout.
- Data charts: `curves: [{ data: [[x, y], ...] }]` draws a polyline through real data; `xCats: ['A', 'B']` with
  `bars: [{ x: 0, y: 3, label: '3' }, ...]` draws a bar chart (category `i` sits at `x = i + 0.5`; bars grow from zero).
- `p.toStage(x, y)` converts data to stage pixels so DOM labels or an equation can be pinned to a point.
- Text is `size` px on the canvas: pick it for the phone (about 38-42 in tall frames).

## Diagram

```js
// array with pointers and swaps
S.arr = EDU.diagram.array(root, {
  x: 140, y: 330, w: W - 280, cell: C.pick(185, 140, 180), cols: C.pick(8, 8, 4), at: 'array', values: [2, 5, 8, 12, 16, 23, 38, 56],
  pointers: [{ label: 'lo', side: 'below', color: 'hi', stops: [['ptrs', 0], ['look2', 4]] },       // stops name SLOTS
             { label: 'mid', side: 'above', color: 'accent', stops: [['look1', 3], ['look2', 5]] }],
  swaps: [{ at: 'sw1', i: 0, j: 3 }],                                                                // cells trade places along an arc
  tones: [{ at: 'look1', cells: [3], tone: 'hi' }, { at: 'look2', cells: [0, 1, 2, 3], tone: 'dim' }],
});
// tree from { id, kids }
S.tree = EDU.diagram.tree(root, { tree: { id: 'r', kids: [{ id: 'a' }, { id: 'b' }] }, x, y, w, h, size: 100, at: 'tree', directed: true,
  labels: { r: '8', a: '4', b: '12' }, tones: { r: [['v1', 'hi']] }, pointers: [{ label: 'node', stops: [['v1', 'r']], side: 'above' }] });
// anything else: nodes, edges, labels, pointers by hand
S.g = EDU.diagram(root, { x, y, w, h, nodes: [{ id: 'a', label: 'A', x: 200, y: 100, shape: 'circle', size: 100, at: 'n1' }],
  edges: [{ from: 'a', to: 'b', at: 'e1', directed: true, label: 'w=3' }] });
```

- Tones: `ink` (default), `hi` (being looked at), `accent` (the answer), `dim` (left behind: recedes to a third, never
  vanishes). Each is a spring from its `at`; a cell can go `hi` then `ink` then `dim`.
- `moves: [[when, {x, y}, preset?, arcPx?]]` retargets a node with velocity kept; `texts: [[when, 'new']]` changes a label
  with a small pop. Edges draw on from their `at`; arrowheads follow the pen. Edge ends stop at the node outline.
- Pointers glide between stops and keep velocity. Two pointers on the same slot use `lane` (0, 1, ...) or opposite
  `side`s. Wrapped arrays (`cols < values.length`) get row gaps sized for the labels and pointers that hang under a row.
- Layout helpers in `lib/layout.js`: `grid`, `tree`, `circle`, `exit`.

## Captions

```js
EDU.captions.overlay({ words: WORDS });                          // a scene on top of the film, whole duration
const cap = EDU.captions(root, { words: WORDS, style: 'pill' });  // or inside one scene; call cap.run(t)
```

Word timings are plain seconds on the film's clock, the shape the narration grid will supply:

```json
[ { "w": "Halve", "t": 0.42, "e": 0.71 }, { "w": "the", "t": 0.71, "e": 0.83 }, { "w": "search.", "t": 0.83 } ]
```

`w` is the word as it should be shown (punctuation attached), `t` its start, `e` its end (optional: the next word's
start, at most 0.6 s later). Also accepted: `word`/`text`, `start`/`s`/`from`, `end`/`to`, or caption cues
`{ cues: [{ text, start, end }] }` (time shared out by word length). With no `words` option the component reads
`C.GRID.words` when the cue grid carries one.

- Pages break at sentence ends, long silences, a comma once the page has some weight, and the line limits. A page rises in as
  its first word starts, the spoken word turns accent and pops, spoken words stay ink, upcoming ones soften, and the page
  is gone 0.2 s before the next one begins.
- Zones: 16:9 and 1:1 bottom-centre; 9:16 sits above the bottom 20 % and left of the right 12 %. Options: `size`, `w`,
  `cx`, `bottom`, `maxLines`, `maxChars`, `maxWords`, `style: 'pill' | 'plain'`, `color`, `active: 'accent' | 'hi'`.
- Reserve the caption strip when laying a scene out: `EDU.zone(position)` already does (see `component-library.md`).

## Verify

After adding a component, run `scripts/render.sh motion <project> all verify` and look at sheets
(`render.mjs --sheet --every 1.5`, both formats, plus `*_phone.jpg`). The usual faults: text too small at phone size,
captions covering content, two pointers on one slot, a hold longer than 8 seconds.
