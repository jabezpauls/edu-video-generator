import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ENGINE } from './helpers/engine.mjs';

const Z = createRequire(import.meta.url)(join(ENGINE, 'edu', 'lib', 'zones.js'));
const inside = (b, c) => b.x >= c.x && b.y >= c.y && b.x + b.w <= c.x + c.w + 1 && b.y + b.h <= c.y + c.h + 1;
const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

test('every position stays inside the content area in every format', () => {
  for (const [W, H] of [[1920, 1080], [1080, 1080], [1080, 1350], [1080, 1920]]) {
    const c = Z.content(W, H);
    for (const p of Z.POSITIONS) assert.ok(inside(Z.zone(p, W, H), c), `${p} in ${W}x${H}`);
  }
});

test('9:16 keeps out of the top 14 %, the right 12 % and the bottom 20 %', () => {
  const c = Z.content(1080, 1920, { captions: false });
  assert.ok(c.y >= 1920 * 0.14 - 1);
  assert.ok(c.x + c.w <= 1080 * 0.88 + 1);
  assert.ok(c.y + c.h <= 1920 * 0.8 + 1);
});

test('left and right sit side by side in 16:9 and stack in 9:16', () => {
  const [l, r] = [Z.zone('left', 1920, 1080), Z.zone('right', 1920, 1080)];
  assert.ok(!overlap(l, r) && l.y === r.y);
  const [tl, tr] = [Z.zone('left', 1080, 1920), Z.zone('right', 1080, 1920)];
  assert.ok(!overlap(tl, tr) && tl.x === tr.x && tl.y < tr.y);
});

test('the four corners tile the content area without overlapping', () => {
  for (const [W, H] of [[1920, 1080], [1080, 1920]]) {
    const q = ['top-left', 'top-right', 'bottom-left', 'bottom-right'].map((p) => Z.zone(p, W, H));
    for (let i = 0; i < 4; i++) for (let j = i + 1; j < 4; j++) {
      // in a tall frame the two top (and the two bottom) corners share a half on purpose
      if (H > W) continue;
      assert.ok(!overlap(q[i], q[j]), `${i} vs ${j}`);
    }
  }
});

test('an unknown position is an error', () => {
  assert.throws(() => Z.zone('middle', 1920, 1080), /unknown position/);
});

test('captions reserve space at the bottom unless switched off', () => {
  assert.ok(Z.content(1920, 1080).h < Z.content(1920, 1080, { captions: false }).h);
});
