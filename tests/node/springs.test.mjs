import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const ref = JSON.parse(readFileSync(join(root, 'tests', 'fixtures', 'spring_reference.json'), 'utf8'));
const tsPath = join(root, 'skills', 'educational-video', 'templates', 'remotion', 'springs.ts');

// springs.ts imports hooks from "remotion", which is not installed in the repo. Strip the import
// and the hook, and load the pure part through Node's TypeScript support.
const skip = process.features.typescript ? false : 'needs a Node with built-in TypeScript (22.18+)';

async function load() {
  const { stripTypeScriptTypes } = await import('node:module');
  let src = readFileSync(tsPath, 'utf8')
    .replace(/^import .*remotion.*$/m, '')
    .replace(/\/\*\* Hook form[\s\S]*$/, '');
  src = stripTypeScriptTypes(src);
  return import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));
}

test('springs.ts matches the reference step response', { skip }, async () => {
  const S = await load();
  for (const [name, r] of Object.entries(ref.presets)) {
    assert.deepEqual(S.SPRING[name], { response: r.response, damping: r.damping });
    ref.taus.forEach((tau, i) => {
      assert.ok(Math.abs(S.step(tau, name) - r.step[i]) < 1e-9, `${name} at ${tau}s`);
    });
  }
});

test('springs.ts settle times match the reference', { skip }, async () => {
  const S = await load();
  for (const [name, r] of Object.entries(ref.presets)) {
    assert.ok(Math.abs(S.settle(name, ref.eps) - r.settle) < 1e-9, name);
  }
});

test('springs.ts behaviour: rest before release, heavy never overshoots, playful does', { skip }, async () => {
  const S = await load();
  const peak = (p) => { let m = 0; for (let t = 0; t < 3; t += 1e-3) m = Math.max(m, S.step(t, p)); return m; };
  assert.equal(S.step(0, 'default'), 0);
  assert.equal(S.step(-1, 'snappy'), 0);
  assert.ok(peak('heavy') <= 1 + 1e-12);
  assert.ok(peak('snappy') - 1 < 0.02);
  assert.ok(peak('playful') - 1 > 0.1);
  assert.equal(S.spr(30, 30, 'heavy', 1), 0);
  assert.ok(Math.abs(S.spr(300, 30, 'heavy') - 1) < 1e-6);
});

test('springs.ts track keeps velocity through a new key', { skip }, async () => {
  const S = await load();
  const keys = [[0, 0], [0.1, 100], [0.2, -50]];
  const f = (t) => S.track(t, keys, 'default');
  const v = (t) => (f(t + 1e-5) - f(t - 1e-5)) / 2e-5;
  assert.ok(Math.abs(f(0.2 - 1e-6) - f(0.2 + 1e-6)) < 1e-2);
  assert.ok(Math.abs(v(0.2 + 1e-5) - v(0.2 - 1e-5)) < 5);
  assert.ok(Math.abs(f(5) + 50) < 1e-6);
  assert.throws(() => S.step(1, 'bouncy'), /unknown preset/);
});
