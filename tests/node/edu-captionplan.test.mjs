import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ENGINE } from './helpers/engine.mjs';

const CP = createRequire(import.meta.url)(join(ENGINE, 'edu', 'lib', 'captionplan.js'));
const W = (s) => s.split(' ').map((w, i) => ({ w, t: i * 0.4, e: i * 0.4 + 0.3 }));

test('normalize accepts the alternative field names and fills missing ends', () => {
  const n = CP.normalize([{ word: 'b', start: 1 }, { text: 'a', from: 0, to: 0.5 }]);
  assert.deepEqual(n, [{ w: 'a', t: 0, e: 0.5 }, { w: 'b', t: 1, e: 1.6 }]);
});

test('normalize never lets a word run into the next one', () => {
  const n = CP.normalize([{ w: 'a', t: 0, e: 2 }, { w: 'b', t: 0.5 }]);
  assert.equal(n[0].e, 0.5);
});

test('normalize rejects words without text or start', () => {
  assert.throws(() => CP.normalize([{ t: 1 }]), /no text/);
  assert.throws(() => CP.normalize([{ w: 'x' }]), /no start/);
});

test('cues are split into words in proportion to their length', () => {
  const w = CP.fromCues([{ text: 'aa bbbb', start: 0, end: 9 }]);
  assert.equal(w.length, 2);
  assert.equal(w[0].t, 0); assert.ok(Math.abs(w[0].e - 3.375) < 1e-9); assert.ok(Math.abs(w[1].e - 9) < 1e-9);
});

test('pages break at sentence ends and keep to the line limit', () => {
  const words = CP.normalize(W('Halve the list. Then look again at the middle value now'));
  const pages = CP.pages(words, { maxChars: 14, maxLines: 2 });
  assert.deepEqual(pages[0].words, [0, 1, 2]);
  assert.ok(pages.every((p) => p.lines.length <= 2));
  assert.ok(pages.every((p) => p.lines.flat().length === p.words.length));
  assert.deepEqual(pages.flatMap((p) => p.words), words.map((_, i) => i));
});

test('a long silence closes the page, and a page ends before the next begins', () => {
  const words = CP.normalize([{ w: 'one', t: 0, e: 0.3 }, { w: 'two', t: 0.3, e: 0.6 }, { w: 'three', t: 2, e: 2.3 }]);
  const p = CP.pages(words);
  assert.equal(p.length, 2);
  assert.ok(p[0].to <= p[1].from);
  const tight = CP.pages(CP.normalize(W('a b c d')), { maxWords: 2, hold: 5 });
  assert.ok(tight[0].to <= tight[1].from);
});

test('activeIndex is the word being spoken, -1 in a gap', () => {
  const words = CP.normalize([{ w: 'a', t: 0, e: 0.3 }, { w: 'b', t: 0.5, e: 0.8 }]);
  assert.equal(CP.activeIndex(words, 0.1), 0);
  assert.equal(CP.activeIndex(words, 0.4), -1);
  assert.equal(CP.activeIndex(words, 0.6), 1);
  assert.equal(CP.activeIndex(words, 5), -1);
});
