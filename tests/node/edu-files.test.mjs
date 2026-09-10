import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { ENGINE } from './helpers/engine.mjs';

test('the pure edu libraries load under node and expose what the components call', () => {
  const req = createRequire(import.meta.url);
  const want = { 'termplan.js': ['match', 'plan'], 'tokens.js': ['tokenize', 'html'], 'plotmath.js': ['ticks', 'sample', 'truncate'],
    'layout.js': ['grid', 'tree', 'circle', 'exit'], 'color.js': ['parse', 'lerp'], 'captionplan.js': ['normalize', 'pages', 'activeIndex'] };
  const files = readdirSync(join(ENGINE, 'edu', 'lib')).sort();
  assert.deepEqual(files, Object.keys(want).sort());
  for (const [f, names] of Object.entries(want)) {
    const m = req(join(ENGINE, 'edu', 'lib', f));
    for (const n of names) assert.equal(typeof m[n], 'function', `${f} exports ${n}`);
  }
});

test('index.html loads the libraries before the components that use them', () => {
  const page = readFileSync(join(ENGINE, 'index.html'), 'utf8');
  const order = [...page.matchAll(/<script src="([^"]+)"/g)].map((m) => m[1]);
  const at = (f) => { const i = order.indexOf(f); assert.ok(i >= 0, `${f} is loaded`); return i; };
  assert.ok(at('core.js') < at('edu/edu.js'));
  assert.ok(at('vendor/katex/katex.min.js') < at('edu/equation.js'));
  const uses = { 'edu/equation.js': 'termplan', 'edu/code.js': 'tokens', 'edu/plot.js': 'plotmath', 'edu/diagram.js': 'layout', 'edu/captions.js': 'captionplan' };
  for (const [comp, lib] of Object.entries(uses)) assert.ok(at(`edu/lib/${lib}.js`) < at(comp), `${lib} before ${comp}`);
  assert.ok(at('edu/lib/color.js') < at('edu/diagram.js'));
  assert.ok(at('edu/edu.js') < at('film.js'));
});

test('every component file declares itself on EDU', () => {
  for (const [f, name] of [['equation', 'equation'], ['code', 'code'], ['plot', 'plot'], ['diagram', 'diagram'], ['captions', 'captions']]) {
    assert.match(readFileSync(join(ENGINE, 'edu', `${f}.js`), 'utf8'), new RegExp(`E\\.${name} = `));
  }
});
