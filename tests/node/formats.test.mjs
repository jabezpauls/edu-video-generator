import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const tsPath = join(root, 'skills', 'educational-video', 'templates', 'remotion', 'formats.ts');
const skip = process.features.typescript ? false : 'needs a Node with built-in TypeScript (22.18+)';

async function load() {
  const { stripTypeScriptTypes } = await import('node:module');
  const src = stripTypeScriptTypes(
    readFileSync(tsPath, 'utf8')
      .replace(/^import .*remotion.*$/m, '')
      .replace(/\/\*\* Hook form[\s\S]*$/, ''),
  );
  return import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));
}

test('sizes and composition ids', { skip }, async () => {
  const F = await load();
  assert.deepEqual(F.SIZES['9x16'], { width: 1080, height: 1920 });
  assert.equal(F.compositionId('Scene01', '16x9'), 'Scene01');
  assert.equal(F.compositionId('Scene01', '9x16'), 'Scene01-9x16');
  for (const id of F.FORMAT_IDS) assert.equal(F.formatIdFromSize(F.SIZES[id].width, F.SIZES[id].height), id);
  assert.equal(F.formatIdFromSize(1280, 720), '16x9');
  assert.equal(F.formatIdFromSize(720, 1280), '9x16');
});

test('orientation and pick (4x5 shares the square value)', { skip }, async () => {
  const F = await load();
  assert.deepEqual(['16x9', '1x1', '4x5', '9x16'].map((i) => F.getFormat(i).orientation), ['wide', 'square', 'tall', 'tall']);
  assert.equal(F.getFormat('4x5').pick('w', 's', 't'), 's');
  assert.equal(F.getFormat('9x16').pick('w', 's', 't'), 't');
  assert.equal(F.getFormat('16x9').pick('w', 's', 't'), 'w');
  assert.equal(F.getFormat('9x16').pick('w'), 'w');
  assert.equal(F.getFormat('9x16').pick('w', 's'), 's');
  assert.equal(F.getFormat('1x1').pick(0, 0, 5), 0);
});

test('9x16 safe area keeps clear of platform UI', { skip }, async () => {
  const F = await load();
  const f = F.getFormat('9x16');
  assert.equal(f.safe.top, Math.round(0.14 * 1920));
  assert.equal(f.safe.bottom, Math.round(0.2 * 1920));
  assert.equal(f.safe.right, Math.round(0.12 * 1080));
  assert.equal(f.safe.px, `${f.safe.top}px ${f.safe.right}px ${f.safe.bottom}px ${f.safe.left}px`);
  assert.equal(f.safe.width, 1080 - f.safe.left - f.safe.right);
  assert.equal(F.getFormat('16x9').safe.left, Math.round(0.05 * 1920));
});

test('safe-area overrides: per format beats all beats default', { skip }, async () => {
  const F = await load();
  const o = { all: { left: 0.1 }, '9x16': { bottom: 0.3 } };
  assert.deepEqual(F.getFormat('9x16', o).safeFrac, { top: 0.14, bottom: 0.3, left: 0.1, right: 0.12 });
  assert.equal(F.getFormat('16x9', o).safeFrac.left, 0.1);
  assert.equal(F.getFormat('16x9', o).safeFrac.bottom, 0.05);
});
