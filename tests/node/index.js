// Entry point so `node --test tests/node` works on every supported Node
// version: newer releases treat a directory argument as a module path rather
// than expanding it, so load the suites explicitly.
import { readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
for (const f of readdirSync(here).filter((n) => n.endsWith('.test.mjs')).sort()) {
  await import(pathToFileURL(join(here, f)).href);
}
