// STARTER LESSON: binary search, silent. Replace these scenes with the approved storyboard. It runs end to end on a
// fresh scaffold and shows the house patterns for each teaching component:
//   s01  masked type that rises on marks (the hook is on frame 0)
//   s02  EDU.diagram.array: cells, lo / mid / hi pointers that glide and keep velocity, tones for "looking" and "left behind"
//   s03  EDU.code: typing on, then a focus band that steps through the lines being explained
//   s04  EDU.equation: per-term reveal, a step swap where shared terms glide, a highlight
//   s05  EDU.plot: axes, a curve drawn over time, a point, a guide, a marker that tracks along the curve
//   all  EDU.captions: burned-in captions from a word list (here generated from SCRIPT; later from the narration grid)
// Everything is a pure function of time (no timers, no Math.random, nothing mutated in run()), re-blocked per format
// with C.pick(wide, square, tall). Scene names follow the storyboard ids (s01, s02, ...) so
// `render.sh motion <project> 02` can find them. Timing lives in timeline.json marks, not in this file.
(() => {
  const { W, H, pick, put, reg, el, scene, seg, ease } = C;
  const { line, rise } = TYPE;
  const PAD = pick(140, 80, 70);                       // left margin: type is never centred on an empty background
  const TALL = H > W;

  // ------------------------------------------------------------ s01: the hook (frame 0 is never empty)
  scene({
    name: 's01', from: 'hook', to: 'array',
    build(root, S) {
      S.head = el('div', { class: 'abs' }, root); reg(S.head);
      // portrait frames break the title into two lines instead of shrinking it
      S.title = TALL
        ? [line(S.head, 'Halve the', { x: PAD, y: 520, size: 190 }), line(S.head, 'search.', { x: PAD, y: 700, size: 190, accent: [0] })]
        : [line(S.head, 'Halve the search.', { x: PAD, y: 330, size: 210, accent: [2] })];
      S.sub = line(S.head, 'Binary search on a sorted list', { x: PAD + 6, y: pick(610, 640, 930), size: pick(60, 52, 54), cls: 'ui', color: 'var(--ink-2)' });
    },
    run(t, S) {
      // word 0 is released before t = 0, so frame 0 already shows it
      S.title.forEach((L, i) => rise(t, L, i ? 'hook_w2' : -0.3, null, { stagger: 0.1 }));
      rise(t, S.sub, 'sub', null, { preset: 'snappy' });
      put(S.head, { s: 1 + 0.04 * seg(t, 'hook', 'array') });   // a held title keeps drifting
    },
  });

  // ------------------------------------------------------------ s02: stepping through the list (diagram)
  const LIST = [2, 5, 8, 12, 16, 23, 38, 56], TARGET = 56;
  const LOOKS = ['look1', 'look2', 'look3', 'look4'];
  const LO = [0, 4, 6, 7], MID = [3, 5, 6, 7];            // lo and the middle at each look
  scene({
    name: 's02', from: 'array', to: 'code',
    build(root, S) {
      S.goal = line(root, `Find ${TARGET}`, { x: PAD, y: pick(130, 200, 330), size: pick(96, 90, 110) });
      // cells the search has left behind recede (dim) but never vanish: the list stays readable
      const tones = [];
      LOOKS.forEach((w, k) => {
        tones.push({ at: w, cells: [MID[k]], tone: 'hi' });
        if (k + 1 < LOOKS.length) tones.push({ at: LOOKS[k + 1], cells: [MID[k]], tone: 'ink' });
        const dead = LIST.map((_, i) => i).filter((i) => i < LO[Math.min(k + 1, 3)] && i >= (k ? LO[k] : 0));
        if (k < 3) tones.push({ at: LOOKS[k + 1], cells: dead, tone: 'dim' });
      });
      tones.push({ at: 'found', cells: [7], tone: 'accent' });
      S.arr = EDU.diagram.array(root, {
        x: PAD, y: pick(330, 460, 390), w: W - 2 * PAD, h: pick(520, 560, 700), cell: pick(185, 140, 180), cols: pick(8, 8, 4), rowGap: TALL ? 290 : undefined, at: 'array', values: LIST, tones,
        pointers: [
          { label: 'lo', side: 'below', color: 'hi', stops: [['ptrs', 0], ...LO.slice(1).map((s, k) => [LOOKS[k + 1], s])] },
          { label: 'mid', side: TALL ? 'above' : 'below', color: 'accent', lane: TALL ? 0 : 1, stops: MID.map((s, k) => [LOOKS[k], s]) },
          { label: 'hi', side: 'above', color: 'ink2', lane: TALL ? 1 : 0, stops: [['ptrs', 7]] },
        ],
      });
    },
    run(t, S) {
      rise(t, S.goal, 'goal', null, { preset: 'snappy' });
      S.arr.run(t);
      put(S.root, { s: 1 + 0.03 * seg(t, 'array', 'code') });
    },
  });

  // ------------------------------------------------------------ s03: the same search as code
  const CODE = `def binary_search(xs, target):
    lo, hi = 0, len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] == target:
            return mid
        if xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1`;
  scene({
    name: 's03', from: 'code', to: 'eq',
    build(root, S) {
      S.k = EDU.code(root, {
        x: pick(120, 60, 50), y: pick(50, 330, 330), w: pick(1300, W - 120, W - 100), size: pick(42, 38, 42), lang: 'python', code: CODE,
        reveal: { mode: 'type', from: 'code_in', to: 'code_done' },
        focus: [{ at: 'cf1', lines: [3, 4] }, { at: 'cf2', lines: [5, 6] }, { at: 'cf3', lines: [7, 8] }, { at: 'cf4', lines: [9, 10] }, { at: 'cf5', lines: null }],
      });
    },
    run(t, S) { S.k.run(t); },
  });

  // ------------------------------------------------------------ s04: the idea as an equation
  scene({
    name: 's04', from: 'eq', to: 'plot',
    build(root, S) {
      const size = pick(200, 150, 190), x = PAD, y = pick(300, 400, 420);
      S.eq = EDU.equation(root, {
        x, y, w: W - 2 * PAD, size, align: 'left',
        steps: [
          { tex: '\\term{pow}{2^{k}} \\term{eq}{=} \\term{n}{n}', at: 'eq1', reveal: { pow: 'eq1', n: 'eq1_n' } },
          { tex: '\\term{k}{k} \\term{eq}{=} \\term{log}{\\log_2} \\term{n}{n}', at: 'eq2' },
        ],
        hi: [{ term: 'n', from: 'hl', to: 'plot-0.5', tone: 'hi' }],
      });
      S.note = line(root, 'k = looks, n = items', { x: PAD + 6, y: y + size * 1.7, size: pick(60, 54, 58), cls: 'ui', color: 'var(--ink-2)' });
    },
    run(t, S) {
      S.eq.run(t);
      rise(t, S.note, 'eq_note', null, { preset: 'snappy' });
    },
  });

  // ------------------------------------------------------------ s05: and as a plot
  scene({
    name: 's05', from: 'plot', to: 'end',
    build(root, S) {
      S.p = EDU.plot(root, {
        x: pick(140, 60, 40), y: pick(100, 330, 290), w: W - pick(280, 120, 80), h: pick(700, 800, 800), xr: [0, 16], yr: [0, 5], xLabel: 'n', yLabel: 'looks', size: pick(36, 38, 42),
        axes: { at: 'axes' },
        curves: [{ fn: (n) => Math.log2(n), from: 1, at: 'curve', dur: 1.8, color: 'accent', label: 'log₂ n' }],
        points: [{ x: 8, y: 3, at: 'pt', label: '8 items: 3 looks', color: 'hi', align: 'right' }],
        segments: [{ from: [8, 0], to: [8, 3], at: 'pt', dash: [10, 10], color: 'hi' }],
        markers: [{ curve: 0, stops: [['m1', 4], ['m2', 16]], drop: true, label: (n, k) => `n=${Math.round(n)}: ${k.toFixed(1)} looks` }],
      });
    },
    run(t, S) { S.p.run(t); },
  });

  // ------------------------------------------------------------ captions: one overlay for the whole film
  // The word list is data: [{ w, t, e }] in seconds. Here it is generated from SCRIPT (a mark and the words said from it);
  // with narration it comes from the grid and nothing else in this file changes.
  const SCRIPT = [
    ['hook', 'Halve the search. That is the whole trick.'],
    ['goal', 'Find fifty six. Look in the middle.'],
    ['look1', 'Twelve: too small. Go right.'],
    ['look2', 'Twenty three. Right again.'],
    ['look3', 'Thirty eight. Right again.'],
    ['look4', 'Fifty six. Found it in four looks.'],
    ['code_in', 'Here it is in code.'],
    ['cf1', 'Take the middle.'], ['cf2', 'Equal: return it.'], ['cf3', 'Too small: move lo up.'], ['cf4', 'Too big: move hi down.'],
    ['eq1', 'k looks cover two to the k items.'],
    ['eq2', 'So looks equal log base two of n.'],
    ['curve', 'Doubling the list adds one look.'],
    ['pt', 'Eight items, three looks.'], ['m1', 'Sixteen, four.'], ['m2', 'That is why halving wins.'],
  ];
  const words = [];
  SCRIPT.forEach(([mark, text], i) => {
    const t0 = C.at(mark), room = (SCRIPT[i + 1] ? C.at(SCRIPT[i + 1][0]) : C.DUR) - t0 - 0.25;
    const ws = text.split(' '), dur = ws.map((w) => 0.14 + 0.035 * w.length + (/[.:,]$/.test(w) ? 0.22 : 0));
    const k = Math.min(1, room / dur.reduce((a, b) => a + b, 0));
    let t = t0;
    ws.forEach((w, j) => { words.push({ w, t: +t.toFixed(3), e: +(t + dur[j] * k).toFixed(3) }); t += dur[j] * k; });
  });
  EDU.captions.overlay({ words });

  C.start();
})();
