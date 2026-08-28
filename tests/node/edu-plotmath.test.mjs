import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ENGINE } from './helpers/engine.mjs';

const P = createRequire(import.meta.url)(join(ENGINE, 'edu', 'lib', 'plotmath.js'));

test('ticks use 1-2-5 steps and stay inside the range', () => {
  assert.deepEqual(P.ticks(0, 10, 5).values, [0, 2, 4, 6, 8, 10]);
  assert.deepEqual(P.ticks(-1, 1, 4).values, [-1, -0.5, 0, 0.5, 1]);
  assert.equal(P.ticks(0, 100, 5).step, 20);
  assert.ok(P.ticks(0.3, 7.2, 5).values.every((v) => v >= 0.3 && v <= 7.2));
});

test('tick labels drop trailing zeros and use a minus sign', () => {
  assert.equal(P.fmt(-0.5, 0.5), '−0.5');
  assert.equal(P.fmt(4, 2), '4');
  assert.equal(P.fmt(0, 0.5), '0');
  assert.equal(P.fmt(1.5, 0.5), '1.5');
});

test('sampling breaks at an asymptote instead of drawing across it', () => {
  const pieces = P.sample((x) => 1 / x, -2, 2, 400, [-4, 4]);
  assert.equal(pieces.length, 2);
  assert.ok(pieces[0].every(([x]) => x < 0) && pieces[1].every(([x]) => x > 0));
});

test('sampling skips undefined values', () => {
  const pieces = P.sample(Math.log, -1, 4, 100, [-3, 3]);
  assert.equal(pieces.length, 1);
  assert.ok(pieces[0][0][0] > 0);
});

test('truncate draws a fraction of the length and reports the pen tip', () => {
  const polys = [[[0, 0], [10, 0]], [[20, 0], [30, 0]]];
  const half = P.truncate(polys, 0.5);
  assert.deepEqual(half.polys, [[[0, 0], [10, 0]]]);
  assert.deepEqual(half.tip.slice(0, 2), [10, 0]);
  const q = P.truncate(polys, 0.75);
  assert.deepEqual(q.polys[1], [[20, 0], [25, 0]]);
  assert.deepEqual(P.truncate(polys, 0), { polys: [], tip: null });
  assert.equal(P.truncate(polys, 1).polys.length, 2);
});
