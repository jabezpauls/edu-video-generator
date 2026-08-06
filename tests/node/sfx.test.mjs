import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const sfx = join(root, 'skills', 'educational-video', 'scripts', 'sfx.mjs');

function project(cues, duration = 4) {
  const dir = mkdtempSync(join(tmpdir(), 'sfx-'));
  writeFileSync(join(dir, 'cues.json'), JSON.stringify({ sr: 48000, duration, cues }));
  return dir;
}
function readWav(file) {
  const b = readFileSync(file);
  assert.equal(b.toString('ascii', 0, 4), 'RIFF');
  const ch = b.readUInt16LE(22), sr = b.readUInt32LE(24), bits = b.readUInt16LE(34), fmt = b.readUInt16LE(20);
  const n = (b.length - 44) / (ch * 4);
  const s = new Float32Array(n * ch);
  for (let i = 0; i < s.length; i++) s[i] = b.readFloatLE(44 + i * 4);
  return { ch, sr, bits, fmt, n, s };
}
const energy = (w, t0, t1) => {
  let e = 0;
  for (let i = Math.floor(t0 * w.sr); i < Math.min(w.n, Math.floor(t1 * w.sr)); i++) e += w.s[i * 2] ** 2 + w.s[i * 2 + 1] ** 2;
  return e;
};

test('every sound type renders audible, bounded audio at its cue', () => {
  for (const type of ['pop', 'click', 'tick', 'whoosh', 'chime', 'thump']) {
    const dir = project([{ t: 1.5, type, gain: 0.8 }]);
    execFileSync('node', [sfx, dir]);
    const w = readWav(join(dir, 'audio', 'sfx.wav'));
    assert.deepEqual([w.ch, w.sr, w.bits, w.fmt], [2, 48000, 32, 3]);
    assert.ok(w.n === 4 * 48000, `${type}: length`);
    assert.ok(energy(w, 1.0, 2.8) > 1e-3, `${type}: has energy around the cue`);
    assert.equal(energy(w, 0, 0.5), 0, `${type}: silent before the cue`);
    assert.ok(w.s.every((v) => Math.abs(v) < 1.2), `${type}: peak sane`);
  }
});

test('a whoosh builds before its cue; a pop does not', () => {
  const run = (type) => {
    const dir = project([{ t: 2, type }]);
    execFileSync('node', [sfx, dir]);
    const w = readWav(join(dir, 'audio', 'sfx.wav'));
    return { before: energy(w, 1.7, 1.99), after: energy(w, 2.0, 2.3) };
  };
  assert.ok(run('whoosh').before > 0);
  assert.equal(run('pop').before, 0);
});

test('output is deterministic and respects --cues / --out', () => {
  const dir = project([{ t: 1, type: 'pop' }, { t: 2, type: 'chime', pan: 0.5 }]);
  writeFileSync(join(dir, 'plan.json'), readFileSync(join(dir, 'cues.json')));
  execFileSync('node', [sfx, dir, '--cues', 'plan.json', '--out', 'a.wav']);
  execFileSync('node', [sfx, dir, '--cues', 'plan.json', '--out', 'b.wav']);
  assert.ok(readFileSync(join(dir, 'a.wav')).equals(readFileSync(join(dir, 'b.wav'))));
});

test('an unknown sound type is an error naming the valid ones', () => {
  const dir = project([{ t: 1, type: 'kazoo' }]);
  const r = spawnSync('node', [sfx, dir], { encoding: 'utf8' });
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /unknown sfx type "kazoo".*pop/s);
});

test('a missing cues file is a clear failure', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sfx-'));
  mkdirSync(join(dir, 'audio'));
  assert.notEqual(spawnSync('node', [sfx, dir], { encoding: 'utf8' }).status, 0);
});
