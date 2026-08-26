import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ENGINE } from './helpers/engine.mjs';

const TP = createRequire(import.meta.url)(join(ENGINE, 'edu', 'lib', 'termplan.js'));
const term = (id, html = id) => ({ kind: 'term', id, html });
const glue = (html) => ({ kind: 'glue', html });

test('a unit matches its twin by kind, id and html', () => {
  const a = [term('a', 'x'), glue('='), term('b', '1')];
  const b = [term('b', '1'), glue('='), term('a', 'x')];
  assert.deepEqual(TP.match(a, b), [2, 1, 0]);
});

test('the same id with different html is a new piece', () => {
  assert.deepEqual(TP.match([term('a', 'x')], [term('a', 'y')]), [-1]);
});

test('repeats match in order', () => {
  const a = [glue('+'), glue('+')], b = [glue('+'), glue('+'), glue('+')];
  assert.deepEqual(TP.match(a, b), [0, 1, -1]);
});

test('new terms enter on their reveal time, else staggered from the step', () => {
  const steps = [{ units: [term('a'), glue('+'), term('b'), term('c')], at: 2, reveal: { b: 3.5 } }];
  const [p] = TP.plan(steps, { stagger: 0.1 });
  assert.deepEqual(p.map((u) => u.enter), [2, 3.5, 3.5, 2.1]);
});

test('glue enters with the next term, or the last one when none follows', () => {
  const steps = [{ units: [glue('('), term('a'), glue('='), term('b'), glue(')')], at: 0, reveal: { a: 1, b: 2 } }];
  const [p] = TP.plan(steps);
  assert.deepEqual(p.map((u) => u.enter), [1, 1, 2, 2, 2]);
});

test('shared pieces glide, the rest exits when the next step starts', () => {
  const steps = [
    { units: [term('a', 'x'), glue('+'), term('b', '1')], at: 0 },
    { units: [term('a', 'x'), glue('='), term('c', '2')], at: 4 },
  ];
  const [s0, s1] = TP.plan(steps, { exitStagger: 0.05 });
  assert.equal(s0[0].to, 0); assert.equal(s0[0].exit, null);
  assert.equal(s0[1].to, -1); assert.equal(s0[1].exit, 4);
  assert.equal(s0[2].exit, 4.05);
  assert.equal(s1[0].from, 0); assert.equal(s1[0].enter, null);
  assert.equal(s1[1].enter, 4.2); assert.equal(s1[2].enter, 4.2);
  assert.equal(s1[2].exit, Infinity);
});
