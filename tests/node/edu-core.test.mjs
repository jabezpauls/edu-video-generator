import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { loadEngine, ENGINE } from './helpers/engine.mjs';

// the engine plus the edu namespace (edu.js and the pure libraries it needs)
function load(opts = {}) {
  const ctx = loadEngine({ GRID: { cues: { 'a.start': 1 } }, TL: { marks: { m: 2 } }, ...opts });
  for (const f of ['edu/lib/zones.js', 'edu/lib/color.js', 'edu/edu.js']) vm.runInContext(readFileSync(join(ENGINE, f), 'utf8'), ctx, { filename: f });
  return ctx;
}

test('EDU.draw is a monotone 0 to 1 that settles at the stated time and never overshoots', () => {
  const { EDU } = load();
  assert.equal(EDU.draw(0.5, 1, 1), 0);
  let prev = 0;
  for (let t = 1; t <= 3; t += 0.01) { const p = EDU.draw(t, 1, 1); assert.ok(p >= prev - 1e-12 && p <= 1 + 1e-12); prev = p; }
  assert.ok(EDU.draw(2.05, 1, 1) > 0.985);
});

test('EDU.draw takes whens: marks and cues', () => {
  const { EDU } = load();
  assert.equal(EDU.draw(1, 'a.start', 1), 0);
  assert.ok(EDU.draw(2, 'a.start', 1) > 0.9);
  assert.equal(EDU.draw(2, 'm', 1), 0);
});

test('mix builds one css colour and clamps the percentage', () => {
  const { EDU } = load();
  assert.equal(EDU.mix('hi', 'ink', 30), 'color-mix(in srgb, var(--hi) 30.00%, var(--ink))');
  assert.match(EDU.mix('hi', 'transparent', 250), /100\.00%/);
  assert.equal(EDU.tone('#123456'), '#123456');
});

test('fitMono shrinks to the width and never grows past max', () => {
  const { EDU } = load();
  assert.equal(EDU.fitMono(10, 10000, 40), 40);
  assert.ok(EDU.fitMono(60, 600, 40) * 60 * 0.602 <= 600);
});

test('zone follows the format the engine was started with', () => {
  const wide = load().EDU.zone('left'), tall = load({ fmt: '9x16' }).EDU.zone('left');
  assert.ok(wide.w < 900, 'left is half the 16:9 frame');
  assert.ok(tall.w > 800, 'left is the full width of the 9:16 content area (stacked, not side by side)');
});

test('the KaTeX faces are queued for loading, once each', () => {
  const { C } = load();
  assert.ok(C.fonts.some((f) => f.includes('KaTeX_Main')) && C.fonts.some((f) => f.includes('KaTeX_Math')));
  assert.equal(new Set(C.fonts).size, C.fonts.length);
});
