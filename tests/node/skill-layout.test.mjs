import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const skill = join(root, 'skills', 'educational-video');

test('SKILL.md has name and description frontmatter', () => {
  const text = readFileSync(join(skill, 'SKILL.md'), 'utf8');
  const m = text.match(/^---\n([\s\S]*?)\n---\n/);
  assert.ok(m, 'frontmatter block present');
  assert.match(m[1], /^name: educational-video$/m);
  assert.match(m[1], /^description:/m);
});

test('every script is executable', () => {
  const dir = join(skill, 'scripts');
  for (const f of readdirSync(dir)) {
    const mode = statSync(join(dir, f)).mode;
    assert.ok(mode & 0o100, `${f} should be executable`);
  }
});

test('every script has a shebang', () => {
  const dir = join(skill, 'scripts');
  for (const f of readdirSync(dir)) {
    const first = readFileSync(join(dir, f), 'utf8').split('\n', 1)[0];
    assert.match(first, /^#!/, `${f} should start with a shebang`);
  }
});
