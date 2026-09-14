import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ENGINE } from './helpers/engine.mjs';

const T = createRequire(import.meta.url)(join(ENGINE, 'edu', 'lib', 'tokens.js'));

test('python: keywords, calls, numbers, strings and comments', () => {
  const [l] = T.tokenize('def f(x): return x + 1  # one', 'python');
  const named = l.filter((t) => t.c).map((t) => `${t.c}:${t.s}`);
  assert.deepEqual(named, ['kw:def', 'fn:f', 'op:(', 'op:)', 'op::', 'kw:return', 'op:+', 'num:1', 'com:# one']);
});

test('every line reassembles to the source exactly', () => {
  const src = 'const a = `x\n  y`;\n/* c\n d */ if (a) { return "s\\"t"; }\n';
  const lines = T.tokenize(src, 'js');
  assert.equal(lines.map((l) => l.map((t) => t.s).join('')).join('\n'), src);
});

test('a multi-line string is split per line and keeps its colour', () => {
  const lines = T.tokenize('x = """a\nb"""', 'py');
  assert.equal(lines.length, 2);
  assert.deepEqual(lines[1].map((t) => t.c), ['str']);
});

test('unknown languages are plain text', () => {
  const [l] = T.tokenize('if x then', 'nonsense');
  assert.ok(l.every((t) => t.c === null || t.c === 'op'));
});

test('html() escapes, and cuts at n characters', () => {
  const [l] = T.tokenize('a < "b"', 'js');
  assert.equal(T.html(l), 'a <span class="t-op">&lt;</span> <span class="t-str">"b"</span>');
  assert.equal(T.html(l, 6), 'a <span class="t-op">&lt;</span> <span class="t-str">"b</span>');
  assert.equal(T.length(l), 7);
});

test('sql keywords are case-insensitive', () => {
  assert.equal(T.tokenize('SELECT a FROM t', 'sql')[0][0].c, 'kw');
});
