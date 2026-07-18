// STARTER LESSON: binary search, silent. Replace these scenes with the approved storyboard. It exists so a fresh
// scaffold renders end to end, and to show the house patterns for teaching:
//   - masked type that rises on cues / marks (a title on frame 0, a recap)
//   - stepping through an algorithm: pointers that glide on springs and keep velocity when retargeted (trk)
//   - one caption per step, each leaving before the next lands (sequential swaps)
//   - emphasis with the highlight hue while the accent marks the answer
//   - per-format layout with C.pick(wide, square, tall)
//   - holds that keep moving (a micro push), never a frozen frame
// Pure function of time: no timers, no Math.random, nothing mutated in run().
// Scene names follow the storyboard ids (s01, s02, ...) so `render.sh motion <project> 02` can find them.
(() => {
  const { W, H, pick, put, reg, el, scene, sp, spHit, trk, seg, lerp, ease, at } = C;
  const { line, rise } = TYPE;
  const PAD = pick(140, 80, 70);                       // left margin: type is never centred on an empty background

  const LIST = [2, 5, 8, 12, 16, 23, 38, 56], TARGET = 56;
  // each step: when it happens, where lo and the middle are, and what the caption says
  const STEPS = [
    { at: 'look1', lo: 0, mid: 3, say: '12 < 56: search right' },
    { at: 'look2', lo: 4, mid: 5, say: '23 < 56: search right' },
    { at: 'look3', lo: 6, mid: 6, say: '38 < 56: search right' },
    { at: 'look4', lo: 7, mid: 7, say: '56 = 56: found it' },
  ];

  // ------------------------------------------------------------ s01: the question (hook on frame 0)
  scene({
    name: 's01', from: 'hook', to: 'array',
    build(root, S) {
      S.head = el('div', { class: 'abs' }, root); reg(S.head);
      S.title = line(S.head, 'Halve the search.', { x: PAD, y: pick(330, 420, 560), size: pick(210, 150, 120), accent: [2] });
      S.sub = line(S.head, 'Binary search on a sorted list', { x: PAD + 6, y: pick(610, 640, 780), size: pick(60, 50, 46), cls: 'ui', color: 'var(--ink-2)' });
    },
    run(t, S) {
      // word 0 is released before t = 0, so frame 0 already shows it
      rise(t, S.title, [-0.3, 'hook_w2', 'hook_w3']);
      rise(t, S.sub, 'sub', null, { preset: 'snappy' });
      put(S.head, { s: 1 + 0.04 * seg(t, 'hook', 'array') });   // a held title keeps drifting
    },
  });

  // ------------------------------------------------------------ s02: stepping through the list
  scene({
    name: 's02', from: 'array', to: 'recap',
    build(root, S) {
      const GAP = pick(16, 10, 10), CELL = Math.min(170, (W - 2 * PAD - 7 * GAP) / 8);
      const Y = pick(430, 600, 720);
      S.cell = CELL; S.gap = GAP; S.y = Y;
      S.goal = line(root, `Find ${TARGET}`, { x: PAD, y: pick(150, 190, 330), size: pick(96, 84, 84) });
      S.step = el('div', { class: 'abs mono', style: `left:${PAD}px;top:${pick(120, 150, 290)}px;font-size:30px;color:var(--ink-2)` }, root);
      reg(S.step, { o: 0 });
      S.cells = LIST.map((v, i) => {
        const c = el('div', { class: 'abs mono', style: `left:${PAD + i * (CELL + GAP)}px;top:${Y}px;width:${CELL}px;height:${CELL}px;border-radius:${CELL * 0.16}px;` +
          `background:var(--card);box-shadow:0 0 0 3px color-mix(in srgb, var(--ink) 14%, transparent), 0 14px 30px -14px rgba(0,0,0,.25);` +
          `display:flex;align-items:center;justify-content:center;font-size:${CELL * 0.4}px;font-weight:600` }, root, String(v));
        return reg(c, { o: 0 });
      });
      S.found = el('div', { class: 'abs', style: `left:0;top:${Y}px;width:${CELL}px;height:${CELL}px;border-radius:${CELL * 0.16}px;background:var(--accent)` }, root);
      reg(S.found, { o: 0 });
      S.mid = el('div', { class: 'abs', style: `top:${Y - 12}px;width:${CELL + 24}px;height:${CELL + 24}px;border-radius:${CELL * 0.2}px;box-shadow:0 0 0 6px var(--hi)` }, root);
      reg(S.mid, { o: 0 });
      const tag = (txt, y, color) => reg(el('div', { class: 'abs mono', style: `top:${y}px;font-size:34px;font-weight:600;color:${color};width:${CELL}px;text-align:center` }, root, txt), { o: 0 });
      S.lo = tag('lo', Y + CELL + 22, 'var(--ink-2)');
      S.hi = tag('hi', Y + CELL + 66, 'var(--ink-2)');
      S.says = STEPS.map((s) => line(root, s.say, { x: PAD, y: Y + CELL + pick(170, 170, 200), size: pick(64, 54, 54), cls: 'ui' }));
      S.x = (i) => PAD + i * (CELL + GAP);
    },
    run(t, S) {
      rise(t, S.goal, 'goal', null, { preset: 'snappy' });
      // the cells pop in left to right (each led so it reads on its stagger); cells the search has left behind recede
      // but never vanish: the list stays readable
      S.cells.forEach((c, i) => {
        const p = spHit(t, at('array') + 0.15 + i * 0.07, 'snappy');
        const left = trk(t, [[0, 0], ...STEPS.map((s) => [s.at, i < s.lo ? 1 : 0, 'snappy'])]);
        put(c, { o: (p > 0.001 ? 1 : 0) * (1 - 0.7 * Math.min(1, Math.max(0, left))), y: 24 * (1 - p), s: 0.9 + 0.1 * p });
      });
      put(S.step, { o: sp(t, 'look1', 'snappy'), text: `step ${Math.max(1, STEPS.filter((s) => t >= at(s.at)).length)} of ${STEPS.length}` });
      // lo, hi and the middle glide between cells; a new target mid-flight keeps the pointer's velocity
      const lo = trk(t, [[0, S.x(0)], ...STEPS.map((s) => [s.at, S.x(s.lo), 'default'])]);
      const mid = trk(t, [[0, S.x(3)], ...STEPS.map((s) => [s.at, S.x(s.mid), 'default'])]);
      const on = sp(t, 'ptrs', 'snappy');
      put(S.lo, { o: on, x: lo }); put(S.hi, { o: on, x: S.x(7) });
      const m = spHit(t, 'look1', 'snappy');
      put(S.mid, { o: m > 0.001 ? 1 : 0, x: mid - 12, s: lerp(0.8, 1, m) });
      // the answer: accent fill swaps in under the cell number, the number turns white
      const f = spHit(t, at('look4') + 0.5, 'snappy');
      put(S.found, { o: f > 0.001 ? 1 : 0, x: S.x(7), s: lerp(0.85, 1, f) });
      put(S.cells[7], { css: { color: f > 0.5 ? '#fff' : 'var(--ink)', background: f > 0.5 ? 'transparent' : 'var(--card)', zIndex: 2 } });
      put(S.found, { css: { zIndex: 1 } });
      // one caption per step; each is gone before the next lands
      S.says.forEach((L, i) => {
        const next = STEPS[i + 1];
        rise(t, L, at(STEPS[i].at) + 0.35, next ? at(next.at) - 0.05 : null, { preset: 'snappy' });
      });
      put(S.root, { s: 1 + 0.03 * seg(t, 'array', 'recap'), x: 0, y: 0 });
    },
  });

  // ------------------------------------------------------------ s03: the takeaway
  scene({
    name: 's03', from: 'recap', to: 'done',
    build(root, S) {
      S.push = el('div', { class: 'abs', style: `width:${W}px;height:${H}px;transform-origin:${PAD}px ${H / 2}px` }, root); reg(S.push);
      S.a = line(S.push, 'Each look halves the list.', { x: PAD, y: H / 2 - pick(200, 190, 230), size: pick(130, 100, 92), accent: [2] });
      S.rule = el('div', { class: 'abs', style: `top:${H / 2 + pick(10, 0, 20)}px;height:12px;background:var(--hi);border-radius:6px` }, S.push); reg(S.rule, { o: 0 });
      S.b = line(S.push, '8 items, 4 looks at most.', { x: PAD + 4, y: H / 2 + pick(70, 60, 90), size: pick(76, 62, 58), cls: 'ui', color: 'var(--ink-2)' });
    },
    run(t, S) {
      put(S.push, { s: 1 + 0.06 * ease.inOut(seg(t, 'recap', 'done')) });
      rise(t, S.a, 'recap', null, { stagger: 0.06 });
      const u = sp(t, at('recap') + 0.5, 'default');
      put(S.rule, { o: u > 0.002 ? 1 : 0, x: PAD + 8, css: { width: (W - 2 * PAD) * 0.45 * u + 'px' } });
      rise(t, S.b, 'recap_b', null, { stagger: 0.05, preset: 'snappy' });
    },
  });

  C.start();
})();
