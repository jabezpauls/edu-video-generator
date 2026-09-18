// Loads the motion engine (lib/motion.js, lib/time.js, core.js, type.js) into a vm context with a tiny fake DOM, so
// the engine's own logic (scenes, registry, commit, formats, cue lookup) can be tested without a browser.
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ENGINE = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..',
  'skills', 'educational-video', 'engines', 'motion');

class FakeStyle {
  set cssText(v) { for (const part of String(v).split(';')) { const i = part.indexOf(':'); if (i > 0) this[part.slice(0, i).trim()] = part.slice(i + 1).trim(); } }
  setProperty(k, v) { this[k] = v; }
  getPropertyValue(k) { return this[k] || ''; }
}

class FakeEl {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.style = new FakeStyle(); this.textContent = ''; this.innerHTML = ''; this.className = ''; }
  appendChild(c) { this.children.push(c); return c; }
  setAttribute(k, v) { this.attrs[k] = v; }
}

export function walk(e, fn) { fn(e); for (const c of e.children) if (c instanceof FakeEl) walk(c, fn); }

/** opts: { fmt, TL, GRID, BEATS, film(ctx) } → the context (ctx.C, ctx.TYPE, ctx.seek once C.start() ran) */
export function loadEngine({ fmt = null, TL = {}, GRID = {}, BEATS = {}, PRESET = null, film = null } = {}) {
  const stage = new FakeEl('div');
  const ctx = {
    console, performance, Math, JSON, Object, Array, Number, String, Error, Promise, URLSearchParams, Float32Array,
    TL: { duration: 10, fps: 60, formats: ['16x9'], ...TL }, GRID, BEATS, PRESET, loadedFaces: [],
    FontFace: class { constructor(family, src, desc) { this.family = family; this.src = src; this.desc = desc; } async load() { return this; } },
    location: { search: fmt ? `?fmt=${fmt}` : '' },
    document: {
      getElementById: () => stage,
      createElement: (t) => new FakeEl(t),
      createTextNode: (s) => ({ text: s, children: [] }),
      images: [], fonts: { load: async () => [{}], ready: Promise.resolve(), add: (f) => ctx.loadedFaces.push(f) },
      body: { classList: { add() {} }, addEventListener() {} },
    },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of ['lib/motion.js', 'lib/time.js']) vm.runInContext(readFileSync(join(ENGINE, f), 'utf8'), ctx, { filename: f });
  ctx.window.TL = ctx.TL; ctx.window.GRID = ctx.GRID; ctx.window.BEATS = ctx.BEATS; ctx.window.PRESET = ctx.PRESET;
  for (const f of ['core.js', 'type.js']) vm.runInContext(readFileSync(join(ENGINE, f), 'utf8'), ctx, { filename: f });
  if (film) film(ctx);
  ctx.stage = stage;
  return ctx;
}

/** Every inline style of every element, as one comparable string (a "frame" for determinism checks). */
export function snapshot(ctx) {
  const rows = [];
  walk(ctx.stage, (e) => { rows.push(JSON.stringify([e.attrs['data-scene'] || e.className, { ...e.style }, e.textContent])); });
  return rows.join('\n');
}
