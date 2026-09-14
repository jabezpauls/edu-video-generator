import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ENGINE } from './helpers/engine.mjs';

const K = createRequire(import.meta.url)(join(ENGINE, 'edu', 'lib', 'color.js'));

test('parses hex and rgb forms', () => {
  assert.deepEqual(K.parse('#e8552b'), [232, 85, 43, 1]);
  assert.deepEqual(K.parse('#fff'), [255, 255, 255, 1]);
  assert.deepEqual(K.parse('rgb(18, 18, 18)'), [18, 18, 18, 1]);
  assert.deepEqual(K.parse('rgba(0, 0, 0, 0.5)'), [0, 0, 0, 0.5]);
});

test('rejects what it cannot read', () => {
  assert.throws(() => K.parse('var(--x)'), /cannot parse/);
});

test('blends and fades', () => {
  assert.equal(K.css(K.lerp(K.parse('#000'), K.parse('#fff'), 0.5)), 'rgba(128, 128, 128, 1)');
  assert.equal(K.fade(K.parse('#000'), 0.25), 'rgba(0, 0, 0, 0.25)');
});
