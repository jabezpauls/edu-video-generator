import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const lib = join(dirname(fileURLToPath(import.meta.url)), '..', '..',
  'skills', 'educational-video', 'engines', 'motion', 'lib');
const { makeTime } = createRequire(import.meta.url)(join(lib, 'time.js'));

const cues = { 's01.start': 0, 's01.end': 6.5, 's02.start': 7, 's02.derivative': 9.25, 's02.derivative#2': 12, 's02.well-known': 10, 's02.p2': 11 };

test('numbers pass through, numeric strings parse', () => {
  const T = makeTime();
  assert.equal(T.at(3.25), 3.25);
  assert.equal(T.at('4'), 4);
  assert.equal(T.at(' -0.5 '), -0.5);
});

test('cues resolve, with and without an offset', () => {
  const T = makeTime({ cues });
  assert.equal(T.at('s02.derivative'), 9.25);
  assert.equal(T.at('s02.derivative#2'), 12);
  assert.ok(Math.abs(T.at('s02.derivative+0.3') - 9.55) < 1e-9);
  assert.ok(Math.abs(T.at('s02.p2 - 0.25') - 10.75) < 1e-9);
  assert.equal(T.at('s02.well-known'), 10, 'a hyphen inside a cue name is not an offset');
  assert.ok(Math.abs(T.at('s02.well-known-0.5') - 9.5) < 1e-9);
});

test('marks can be seconds, cues, or other marks', () => {
  const T = makeTime({
    cues,
    marks: { open: 0.5, idea: 's02.derivative', result: 'idea+2', tail: 'result + 1' },
  });
  assert.equal(T.at('open'), 0.5);
  assert.equal(T.at('idea'), 9.25);
  assert.equal(T.at('result'), 11.25);
  assert.equal(T.at('tail'), 12.25);
  assert.deepEqual(T.resolveMarks(), { open: 0.5, idea: 9.25, result: 11.25, tail: 12.25 });
});

test('unknown names and loops are loud errors', () => {
  const T = makeTime({ cues, marks: { a: 'b', b: 'a' } });
  assert.throws(() => T.at('s09.nothing'), /unknown mark or cue "s09.nothing"/);
  assert.throws(() => T.at('a'), /loop/);
  assert.throws(() => T.at(NaN), /finite/);
  assert.throws(() => T.at({}), /cannot place/);
  assert.throws(() => makeTime({ cues }).at('s02.deriv'), /unknown/);
  assert.match((() => { try { makeTime({ cues }).at('s02.derivativ'); } catch (e) { return e.message; } })(), /did you mean/);
});

test('has() reports whether a name resolves', () => {
  const T = makeTime({ cues });
  assert.equal(T.has('s01.end'), true);
  assert.equal(T.has('nope'), false);
});

test('nominal beat grid from bpm, optional and secondary', () => {
  const T = makeTime({ bpm: 120 });
  assert.equal(T.beat(0), 0);
  assert.equal(T.beat(4), 2);
  assert.equal(T.at('@4'), 2);
  assert.ok(Math.abs(T.at('@4+0.25') - 2.25) < 1e-9);
});

test('measured beat grid interpolates between beats and extrapolates by the period', () => {
  const T = makeTime({ beats: { beat: 0.5, beats: [0.1, 0.62, 1.1, 1.6] } });
  assert.equal(T.beat(0), 0.1);
  assert.ok(Math.abs(T.beat(1.5) - 0.86) < 1e-9);
  assert.ok(Math.abs(T.beat(5) - (1.6 + 2 * 0.5)) < 1e-9);
  assert.ok(Math.abs(T.beat(-1) - (0.1 - 0.5)) < 1e-9);
});
