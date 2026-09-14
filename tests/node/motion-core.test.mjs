import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadEngine, snapshot } from './helpers/engine.mjs';

const GRID = { cues: { 's01.start': 0, 's01.end': 4, 's02.start': 4, 's02.derivative': 5.5, 's02.end': 8 } };
const TL = { duration: 8, marks: { open: 0.5, idea: 's02.derivative', after: 'idea+1' } };

// A small film: two scenes, a spring pop on a cue, a typed line, a hard cut at s02.start.
function film(ctx) {
  const { C, TYPE } = ctx;
  C.scene({
    name: 's01', from: 's01.start', to: 's01.end',
    build(root, S) { S.box = C.el('div', { class: 'box' }, root); C.reg(S.box, { o: 0 }); },
    run(t, S) { const p = C.spHit(t, 'open', 'snappy'); C.put(S.box, { o: p > 0.001 ? 1 : 0, s: 0.9 + 0.1 * p }); },
  });
  C.scene({
    name: 's02', from: 's02.start', to: 's02.end',
    build(root, S) { S.t = C.el('span', {}, root); C.reg(S.t); S.hit = C.el('div', { class: 'hit' }, root); C.reg(S.hit, { o: 0 }); },
    run(t, S) { TYPE.type(t, S.t, 'hello', 's02.start', 'idea'); C.put(S.hit, { o: C.sp(t, 'idea', 'snappy') }); },
  });
  C.start();
}

test('seek is exposed after start, with duration, cuts and resolved marks', async () => {
  const ctx = loadEngine({ TL, GRID, film });
  assert.equal(await ctx.READY, true);
  assert.equal(ctx.DURATION, 8);
  assert.deepEqual([...ctx.CUTS], [4]);
  assert.deepEqual({ ...ctx.MARKS }, { open: 0.5, idea: 5.5, after: 6.5 });
  assert.deepEqual(Array.from(ctx.SCENE_TIMES, (s) => [s.name, s.from, s.to]), [['s01', 0, 4], ['s02', 4, 8]]);
});

test('a spring released on a cue is zero before it and one after it settles', async () => {
  const ctx = loadEngine({ TL, GRID, film });
  await ctx.READY;
  const { C } = ctx;
  assert.equal(C.sp(0.4, 'open', 'snappy'), 0);
  assert.ok(C.sp(2, 'open', 'snappy') > 0.999);
  assert.equal(C.sp(5.4, 's02.derivative'), 0);
  assert.ok(C.sp(7, 'idea') > 0.99);
});

test('spHit leads the cue so the hit reads on it', async () => {
  const ctx = loadEngine({ TL, GRID, film });
  await ctx.READY;
  const { C } = ctx;
  assert.ok(C.leadFor('snappy') >= 3 / 60);
  assert.ok(C.spHit(0.5, 'open', 'snappy') > C.sp(0.5, 'open', 'snappy'));
  assert.ok(C.spHit(0.5, 'open', 'snappy') > 0.3, 'a hit is already half-way on the cue');
});

test('frames are a pure function of t: any order, cold or revisited', async () => {
  const ctx = loadEngine({ TL, GRID, film });
  await ctx.READY;
  const ts = [0, 0.7, 2.2, 4.0, 4.9, 5.6, 6.5, 7.99];
  const cold = ts.map((t) => { ctx.seek(t); return snapshot(ctx); });
  const shuffled = [5, 2, 7, 0, 6, 3, 1, 4];
  for (const i of shuffled) {
    ctx.seek(ts[(i * 3 + 1) % ts.length]);           // disturb: paint something else first
    ctx.seek(ts[i]);
    assert.equal(snapshot(ctx), cold[i], `t=${ts[i]}`);
  }
});

test('scenes are only visible inside their window', async () => {
  const ctx = loadEngine({ TL, GRID, film });
  await ctx.READY;
  const vis = () => ctx.stage.children.map((s) => s.style.visibility !== 'hidden');
  ctx.seek(1); assert.deepEqual(vis(), [true, false]);
  ctx.seek(5); assert.deepEqual(vis(), [false, true]);
});

test('typewriter follows the time source', async () => {
  const ctx = loadEngine({ TL, GRID, film });
  await ctx.READY;
  const text = () => ctx.stage.children[1].children[0].textContent;
  ctx.seek(4.0); assert.equal(text(), '');
  ctx.seek(4.75); assert.equal(text().length, 2);
  ctx.seek(5.6); assert.equal(text(), 'hello');
});

test('pick re-blocks per format (4x5 shares the square value)', () => {
  const want = { '16x9': 'wide', '1x1': 'square', '4x5': 'square', '9x16': 'tall' };
  for (const [fmt, v] of Object.entries(want)) {
    const ctx = loadEngine({ fmt, TL, GRID });
    assert.equal(ctx.C.pick('wide', 'square', 'tall'), v, fmt);
  }
  assert.equal(loadEngine({ fmt: '9x16' }).C.pick(1), 1, 'one value fits every format');
});

test('frame size follows ?fmt= and the first listed format is the default', () => {
  const sizes = { '16x9': [1920, 1080], '1x1': [1080, 1080], '4x5': [1080, 1350], '9x16': [1080, 1920] };
  for (const [fmt, [w, h]] of Object.entries(sizes)) {
    const { C } = loadEngine({ fmt });
    assert.deepEqual([C.W, C.H], [w, h]);
  }
  assert.equal(loadEngine({ TL: { formats: ['9x16', '16x9'] } }).C.FMT, '9x16');
  assert.throws(() => loadEngine({ fmt: '3x2' }), /unknown format/);
});

test('an unknown cue in a scene window fails at start, not mid-render', () => {
  assert.throws(() => loadEngine({
    TL, GRID,
    film: ({ C }) => { C.scene({ name: 'bad', from: 's09.start', to: 's09.end' }); C.start(); },
  }), /unknown mark or cue "s09.start"/);
});

test('trk takes whens and keeps a continuous value across retargets', async () => {
  const ctx = loadEngine({ TL, GRID, film });
  await ctx.READY;
  const f = (t) => ctx.C.trk(t, [[0, 0], ['open', 100], ['idea', 40]]);
  assert.equal(f(0.4), 0);
  assert.ok(Math.abs(f(5.5 - 1e-6) - f(5.5 + 1e-6)) < 1e-2);
  assert.ok(Math.abs(f(9) - 40) < 0.5);
});

test('a settled element carries no transform, a moving one does', async () => {
  const ctx = loadEngine({ TL, GRID, film: (c) => {
    c.C.scene({ name: 's01', from: 0, to: 8, build(root, S) { S.b = c.C.el('div', {}, root); c.C.reg(S.b); },
      run(t, S) { const p = c.C.sp(t, 'open', 'snappy'); c.C.put(S.b, { x: 100 * (1 - p), s: 0.9 + 0.1 * p }); } });
    c.C.start();
  } });
  await ctx.READY;
  const box = () => ctx.stage.children[0].children[0];
  ctx.seek(0.6);
  assert.match(box().style.transform || '', /translate\(/);
  ctx.seek(5);
  assert.equal(box().style.transform || '', '');
});
