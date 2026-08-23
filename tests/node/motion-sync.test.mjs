import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const sync = join(dirname(fileURLToPath(import.meta.url)), '..', '..',
  'skills', 'educational-video', 'scripts', 'sync.mjs');

function project(files) {
  const dir = mkdtempSync(join(tmpdir(), 'sync-'));
  for (const [name, body] of Object.entries(files)) writeFileSync(join(dir, name), typeof body === 'string' ? body : JSON.stringify(body));
  return dir;
}
const run = (dir, ...args) => spawnSync(process.execPath, [sync, '--project', dir, ...args], { encoding: 'utf8' });
// film/data.js is `window.X = <json>;` lines
const data = (dir) => {
  const out = {};
  for (const m of readFileSync(join(dir, 'film/data.js'), 'utf8').matchAll(/^window\.(\w+) = (.*);$/gm)) out[m[1]] = JSON.parse(m[2]);
  return out;
};

test('writes data.js and cues.json from a plain timeline', () => {
  const dir = project({ 'timeline.json': { duration: 10, formats: ['9x16'], marks: { a: 1, b: 'a+2.5' }, sfx: [{ at: 'b', type: 'pop', what: 'x' }] } });
  const r = run(dir);
  assert.equal(r.status, 0, r.stderr);
  const d = data(dir);
  assert.equal(d.TL.duration, 10);
  assert.equal(d.TL.fps, 60);
  assert.deepEqual(d.TL.formats, ['9x16']);
  assert.deepEqual(d.TL.marks, { a: 1, b: 'a+2.5' }, 'marks stay symbolic: the engine resolves them with the same module');
  assert.deepEqual(d.BEATS, {});
  const cues = JSON.parse(readFileSync(join(dir, 'cues.json'), 'utf8'));
  assert.equal(cues.cues.length, 1);
  assert.equal(cues.cues[0].t, 3.5);
  assert.equal(cues.cues[0].type, 'pop');
  assert.match(r.stdout, /3\.500s\s+b/);
});

test('sfx repeats expand to one cue per step and drop cues past the end', () => {
  const dir = project({ 'timeline.json': { duration: 4, marks: { t0: 1 }, sfx: [{ at: 't0', to: 2, every: 0.25, type: 'tick' }, { at: 9, type: 'pop' }] } });
  assert.equal(run(dir).status, 0);
  const cues = JSON.parse(readFileSync(join(dir, 'cues.json'), 'utf8')).cues;
  assert.deepEqual(cues.map((c) => c.t), [1, 1.25, 1.5, 1.75]);
});

test('sfx variation is seeded: two runs write identical cues', () => {
  const dir = project({ 'timeline.json': { duration: 4, sfx: [{ at: 1, type: 'pop' }, { at: 2, type: 'pop' }] } });
  run(dir); const a = readFileSync(join(dir, 'cues.json'), 'utf8');
  run(dir); assert.equal(readFileSync(join(dir, 'cues.json'), 'utf8'), a);
});

test('without narration, storyboard estimates provide scene start and end cues', () => {
  const dir = project({
    'timeline.json': { marks: { second: 's02.start+0.5' } },
    'storyboard.json': { scenes: [{ id: '01', est_duration_s: 6 }, { id: '02', est_duration_s: 8 }] },
  });
  const r = run(dir);
  assert.equal(r.status, 0, r.stderr);
  const d = data(dir);
  assert.equal(d.TL.duration, 14, 'duration defaults to the last scene end');
  assert.deepEqual(d.GRID.cues, { 's01.start': 0, 's01.end': 6, 's02.start': 6, 's02.end': 14 });
  assert.equal(d.GRID.nominal, true);
  assert.match(r.stdout, /6\.500s\s+second/);
});

test('a grid.json replaces the estimates and its cues resolve in marks', () => {
  const dir = project({
    'timeline.json': { marks: { idea: 's02.derivative', result: 'idea + 1.5' } },
    'storyboard.json': { scenes: [{ id: '01', est_duration_s: 6 }, { id: '02', est_duration_s: 8 }] },
    'grid.json': { duration: 12.4, scenes: [{ id: '01', start: 0, end: 5.1 }, { id: '02', start: 5.1, end: 12.4 }], cues: { 's02.derivative': 8.2 } },
  });
  const r = run(dir);
  assert.equal(r.status, 0, r.stderr);
  const d = data(dir);
  assert.equal(d.TL.duration, 12.4);
  assert.equal(d.GRID.cues['s02.start'], 5.1);
  assert.equal(d.GRID.cues['s02.derivative'], 8.2);
  assert.equal(d.GRID.nominal, false);
  assert.match(r.stdout, /9\.700s\s+result/);
});

test('an optional beat grid is passed through for music-synced marks', () => {
  const dir = project({ 'timeline.json': { duration: 8, marks: { drop: '@4' } }, 'beats.json': { beat: 0.5, offset: 0.2 } });
  const r = run(dir);
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(data(dir).BEATS, { beat: 0.5, offset: 0.2 });
  assert.match(r.stdout, /2\.200s\s+drop/);
});

test('an unknown cue fails loudly with exit 1 and writes nothing', () => {
  const dir = project({ 'timeline.json': { duration: 5, marks: { x: 's07.nothing' } } });
  const r = run(dir);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /unknown mark or cue "s07\.nothing"/);
  assert.equal(existsSync(join(dir, 'film/data.js')), false);
});

test('missing timeline, bad JSON and missing duration are reported', () => {
  assert.match(run(project({})).stderr, /timeline\.json not found/);
  assert.match(run(project({ 'timeline.json': '{nope' })).stderr, /not valid JSON/);
  assert.match(run(project({ 'timeline.json': { marks: {} } })).stderr, /no duration/);
});

test('marks outside the film are a warning, not an error', () => {
  const dir = project({ 'timeline.json': { duration: 5, marks: { late: 9 } } });
  const r = run(dir, '--quiet');
  assert.equal(r.status, 0);
  assert.match(r.stderr, /mark "late" is at 9\.00s/);
});

test('grid.json scenes and the storyboard fallback use the same s<NN> prefix as grid.py', () => {
  const dir = project({
    'timeline.json': { marks: { a: 's02.start' } },
    'storyboard.json': { scenes: [{ id: 'intro', est_duration_s: 4 }, { id: '2', est_duration_s: 4 }] },
  });
  assert.equal(run(dir).status, 0);
  assert.deepEqual(Object.keys(data(dir).GRID.cues), ['s01.start', 's01.end', 's02.start', 's02.end']);
  const g = project({
    'timeline.json': { marks: { a: 's02.start' } },
    'grid.json': { duration: 8, scenes: [{ id: 'intro', n: 1, start: 0, end: 4 }, { id: '2', n: 2, start: 4, end: 8 }], cues: {} },
  });
  assert.equal(run(g).status, 0);
  assert.equal(data(g).GRID.cues['s02.start'], 4);
});

test('a cues.json planned by grid.py survives sync unless the timeline declares sfx', () => {
  const plan = { sr: 48000, duration: 5, source: 'grid', cues: [{ t: 1, type: 'pop' }] };
  const dir = project({ 'timeline.json': { duration: 5 }, 'cues.json': plan });
  assert.equal(run(dir).status, 0);
  assert.deepEqual(JSON.parse(readFileSync(join(dir, 'cues.json'), 'utf8')), plan);
  const withSfx = project({ 'timeline.json': { duration: 5, sfx: [{ at: 2, type: 'click' }] }, 'cues.json': plan });
  assert.equal(run(withSfx).status, 0);
  const out = JSON.parse(readFileSync(join(withSfx, 'cues.json'), 'utf8'));
  assert.equal(out.source, 'timeline');
  assert.deepEqual(out.cues.map((c) => c.t), [2]);
});
