import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ENGINE } from './helpers/engine.mjs';

const L = createRequire(import.meta.url)(join(ENGINE, 'edu', 'lib', 'layout.js'));
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);

test('a row of cells shrinks to fit the width', () => {
  const g = L.grid(8, { w: 800, cell: 200 });
  near(g.width, 800);
  assert.ok(g.cell < 200);
  near(g.pos[0].x, g.cell / 2);
  near(g.pos[7].x, 800 - g.cell / 2);
  assert.equal(new Set(g.pos.map((p) => p.y)).size, 1);
});

test('a row keeps the cell size when it already fits', () => {
  assert.equal(L.grid(4, { w: 2000, cell: 100 }).cell, 100);
});

test('cols re-blocks a row into a grid', () => {
  const g = L.grid(8, { cols: 4, w: 800, cell: 200 });
  assert.equal(new Set(g.pos.map((p) => p.y)).size, 2);
  near(g.pos[4].x, g.pos[0].x);
  near(g.height, 2 * g.cell + g.gap);
});

test('tree: leaves take consecutive slots, parents sit between their children', () => {
  const t = L.tree({ id: 'r', kids: [{ id: 'a', kids: [{ id: 'c' }, { id: 'd' }] }, { id: 'b' }] });
  const by = Object.fromEntries(t.nodes.map((n) => [n.id, n]));
  near(by.c.ux, 0); near(by.d.ux, 0.5); near(by.b.ux, 1);
  near(by.a.ux, 0.25); near(by.r.ux, 0.625);
  near(by.r.uy, 0); near(by.c.uy, 1);
  assert.equal(by.c.parent, 'a'); assert.equal(t.leaves, 3); assert.equal(t.depth, 2);
});

test('tree: a lone node is centred', () => {
  const [n] = L.tree({ id: 'x' }).nodes;
  assert.deepEqual([n.ux, n.uy], [0.5, 0.5]);
});

test('circle starts at the top and goes clockwise', () => {
  const [a, b] = L.circle(4, 0, 0, 10);
  near(a.x, 0); near(a.y, -10); near(b.x, 10); near(b.y, 0);
});

test('exit finds where a ray leaves a circle or a box', () => {
  assert.deepEqual(L.exit('circle', 100, 100, 1, 0), { x: 50, y: 0 });
  const e = L.exit('rect', 200, 100, 1, 1);
  near(e.x, 50); near(e.y, 50);
});
