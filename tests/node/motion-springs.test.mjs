import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const engine = join(dirname(fileURLToPath(import.meta.url)), '..', '..',
  'skills', 'educational-video', 'engines', 'motion');
const M = createRequire(import.meta.url)(join(engine, 'lib', 'motion.js'));

const peak = (p) => {
  let m = 0;
  for (let t = 0; t < 3; t += 1e-3) m = Math.max(m, M.step(t, p));
  return m;
};

test('the four presets are defined', () => {
  assert.deepEqual(Object.keys(M.PRESETS).sort(), ['default', 'heavy', 'playful', 'snappy']);
});

test('step is 0 at and before release and settles on 1', () => {
  for (const p of Object.keys(M.PRESETS)) {
    assert.equal(M.step(0, p), 0);
    assert.equal(M.step(-2, p), 0);
    assert.ok(Math.abs(M.step(10, p) - 1) < 1e-9, p);
  }
});

test('overshoot per preset', () => {
  assert.ok(peak('heavy') <= 1 + 1e-12, 'heavy is critically damped');
  assert.ok(peak('snappy') - 1 < 0.02);
  assert.ok(peak('default') - 1 < 0.01);
  assert.ok(peak('playful') - 1 > 0.1);
});

test('unknown preset is an error, custom preset objects work', () => {
  assert.throws(() => M.step(1, 'bouncy'), /unknown preset/);
  assert.ok(M.step(0.2, { response: 0.3, damping: 1.4 }) > 0);
});

test('track retargets without restarting (velocity is continuous)', () => {
  const f = (t) => M.track(t, [[0, 0], [0.1, 100], [0.2, -50]]);
  const v = (t) => (f(t + 1e-5) - f(t - 1e-5)) / 2e-5;
  assert.ok(Math.abs(f(0.2 - 1e-6) - f(0.2 + 1e-6)) < 1e-2);
  assert.ok(Math.abs(v(0.2 + 1e-5) - v(0.2 - 1e-5)) < 5);
  assert.ok(Math.abs(f(5) + 50) < 1e-6);
});

test('closed form: the same t gives the same value in any order', () => {
  const ts = [0.9, 0.1, 0.5, 0.1, 2.2];
  const a = ts.map((t) => M.track(t, [[0, 0], [0.3, 1, 'heavy'], [0.8, 0.4]], 'default'));
  const b = [...ts].reverse().map((t) => M.track(t, [[0, 0], [0.3, 1, 'heavy'], [0.8, 0.4]], 'default')).reverse();
  assert.deepEqual(a, b);
});

test('indicator stretches while moving and settles to its size', () => {
  const stops = [[0, 0, 100], [0.1, 500, 600]];
  let max = 0;
  for (let t = 0.1; t < 1; t += 0.001) max = Math.max(max, M.indicator(t, stops).size);
  assert.ok(max > 150);
  assert.ok(Math.abs(M.indicator(5, stops).size - 100) < 1e-6);
});

test('swapAlpha waits for the morph and is gone before the next one', () => {
  assert.equal(M.swapAlpha(1.0, 1, 2), 0);
  assert.ok(M.swapAlpha(1.5, 1, 2) > 0.99);
  assert.ok(M.swapAlpha(2, 1, 2) < 0.005);
});

test('lib/motion.test.js self-check passes', () => {
  const r = spawnSync(process.execPath, [join(engine, 'lib', 'motion.test.js')], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stdout + r.stderr);
});
