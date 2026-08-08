import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const render = join(dirname(fileURLToPath(import.meta.url)), '..', '..',
  'skills', 'educational-video', 'scripts', 'render.mjs');
const run = (dir, ...args) => spawnSync(process.execPath, [render, '--project', dir, ...args], { encoding: 'utf8' });

test('render.mjs refuses a folder that is not a motion project', () => {
  const r = run(mkdtempSync(join(tmpdir(), 'render-')), '--at', '1');
  assert.equal(r.status, 1);
  assert.match(r.stderr, /not a motion project/);
});

test('render.mjs asks for sync when data.js is missing', () => {
  const dir = mkdtempSync(join(tmpdir(), 'render-'));
  mkdirSync(join(dir, 'film'));
  writeFileSync(join(dir, 'film/index.html'), '<html></html>');
  writeFileSync(join(dir, 'timeline.json'), '{"duration": 3}');
  const r = run(dir, '--at', '1');
  assert.equal(r.status, 1);
  assert.match(r.stderr, /run scripts\/sync\.mjs first/);
});
