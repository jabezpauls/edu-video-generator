#!/usr/bin/env node
// Build the motion engine's inputs from the project's timeline: timeline.json (+ grid.json, beats.json, storyboard.json)
// → film/data.js (window.TL / GRID / BEATS) and cues.json (sound-effect cues in seconds; a plan made by `grid.py cues`
// is left alone unless timeline.json declares sfx).
// Run after ANY change to timeline.json, grid.json or beats.json.   node sync.mjs [--project <dir>] [--quiet]
//
// Time is in SECONDS. A mark in timeline.json is seconds, a cue name, or another mark with an offset
// ("idea+0.3"); lib/time.js defines the syntax and the engine uses the same module, so both always agree.
//
// The cue grid (window.GRID.cues) is where narration plugs in. It is assembled from, lowest to highest priority:
//   1. storyboard.json, when there is no narration yet: sNN.start / sNN.end from the cumulative est_duration_s
//   2. grid.json (written by grid.py) { duration?, scenes: [{ id, n?, start, end }], cues: { "s03.derivative": 12.31, ... } }
// so a film written against 's02.start' or 's02.derivative' keeps working when real speech replaces the estimates.
//
// timeline.json:
//   { title?, duration?, fps?, formats?, marks?: { name: when }, sfx?: [ { at, type, gain?, pitch?, pan?, what? } ] }
//   sfx repeats: { at, to, every: seconds, ... } expands to one cue per step (typing ticks, rolls).
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(`--${k}`); return i < 0 ? d : (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true); };
const ROOT = path.resolve(String(opt('project', process.cwd())));
const QUIET = argv.includes('--quiet');
const HERE = path.dirname(fileURLToPath(import.meta.url));

const fail = (m) => { console.error(`sync: ${m}`); process.exit(1); };
const readJSON = (f, required) => {
  const p = path.join(ROOT, f);
  if (!fs.existsSync(p)) { if (required) fail(`${f} not found in ${ROOT}`); return null; }
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { return fail(`${f} is not valid JSON: ${e.message}`); }
};

// the project's own copy of the time module wins (it is what the film runs); fall back to the skill's
const req = createRequire(import.meta.url);
const timeLib = [path.join(ROOT, 'film/lib/time.js'), path.join(HERE, '../engines/motion/lib/time.js')].find((p) => fs.existsSync(p));
if (!timeLib) fail('lib/time.js not found (is this a motion project? see scaffold_motion.sh)');
const { makeTime } = req(timeLib);

const TL = readJSON('timeline.json', true);
const grid = readJSON('grid.json');
const beats = readJSON('beats.json');
const storyboard = readJSON('storyboard.json');

// ------------------------------------------------------------------ cue grid
const cues = {};
const sceneIds = [];
// scene cue prefix: grid.py names scenes s<NN> from the numeric id (or the 1-based position for
// non-numeric ids), so the storyboard fallback and grid.json scenes must agree with it
const prefix = (sc, i) => 's' + String(Number.isFinite(+sc.n) && sc.n > 0 ? +sc.n : /^\d+$/.test(String(sc.id)) ? +sc.id : i + 1).padStart(2, '0');
const num = (v, what) => { if (!Number.isFinite(v)) fail(`${what} must be a number`); return v; };
if (storyboard && Array.isArray(storyboard.scenes) && !(grid && grid.scenes)) {
  let t = 0;
  storyboard.scenes.forEach((sc, i) => {
    const d = sc.est_duration_s;
    if (!Number.isFinite(d)) return;
    const p = prefix(sc, i);
    sceneIds.push(p);
    cues[`${p}.start`] = +t.toFixed(4); t += d; cues[`${p}.end`] = +t.toFixed(4);
  });
}
if (grid) {
  (grid.scenes || []).forEach((sc, i) => {
    const p = prefix(sc, i);
    sceneIds.push(p);
    cues[`${p}.start`] = num(sc.start, `grid scene ${sc.id} start`);
    cues[`${p}.end`] = num(sc.end, `grid scene ${sc.id} end`);
  });
  for (const [k, v] of Object.entries(grid.cues || {})) cues[k] = num(v, `grid cue ${k}`);
}
const lastEnd = Math.max(0, ...Object.entries(cues).filter(([k]) => k.endsWith('.end')).map(([, v]) => v));
const duration = TL.duration ?? grid?.duration ?? (lastEnd > 0 ? lastEnd : null);
if (!(duration > 0)) fail('no duration: set "duration" in timeline.json (or provide storyboard est_duration_s / grid.json)');
const fps = TL.fps || 60;
const formats = TL.formats || ['16x9'];
const tl = { ...TL, duration, fps, formats };

// ------------------------------------------------------------------ resolve (loud on any unknown name)
const T = makeTime({ marks: TL.marks, cues, beats: beats || {}, bpm: TL.bpm });
let marks;
try { marks = T.resolveMarks(); } catch (e) { fail(e.message); }
const late = Object.entries(marks).filter(([, t]) => t > duration + 1e-6 || t < -1e-6);

const rnd = (() => { let a = 2026; return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; })();
const events = [];
for (const ev of TL.sfx || []) {
  if (!ev.type) fail(`sfx event without a type: ${JSON.stringify(ev)}`);
  if (ev.every) {
    if (!(ev.every > 0) || ev.to == null) fail(`sfx repeat needs "to" and a positive "every": ${JSON.stringify(ev)}`);
    let end; try { end = T.at(ev.to); } catch (e) { fail(e.message); }
    for (let x = T.at(ev.at); x < end - 1e-9; x += ev.every) events.push({ ...ev, t: x });
  } else {
    let x; try { x = T.at(ev.at); } catch (e) { fail(e.message); }
    events.push({ ...ev, t: x });
  }
}
const sfx = events.filter((e) => e.t < duration).sort((a, b) => a.t - b.t).map((e) => ({
  t: +e.t.toFixed(5), type: e.type, gain: e.gain ?? 0.8,
  pitch: e.pitch ?? +(0.94 + rnd() * 0.12).toFixed(3), pan: e.pan ?? +((rnd() - 0.5) * 0.5).toFixed(3),
  at: typeof e.at === 'string' ? e.at : null, what: e.what || '',
}));

// ------------------------------------------------------------------ write
// cues.json is shared with `grid.py cues` (same shape, tagged by "source"). A plan derived from storyboard beats
// by grid.py is kept unless the timeline declares its own sfx, which then win because they are placed on the film's marks.
let keepGridPlan = false;
const cuesPath = path.join(ROOT, 'cues.json');
if (fs.existsSync(cuesPath) && !(TL.sfx || []).length) {
  try { keepGridPlan = JSON.parse(fs.readFileSync(cuesPath, 'utf8')).source === 'grid'; } catch { /* unreadable: rewrite */ }
}
if (!keepGridPlan) fs.writeFileSync(cuesPath, JSON.stringify({ sr: 48000, duration, source: 'timeline', cues: sfx }, null, 1) + '\n');
fs.mkdirSync(path.join(ROOT, 'film'), { recursive: true });
const dataGrid = { cues, scenes: sceneIds, nominal: !grid };
fs.writeFileSync(path.join(ROOT, 'film/data.js'),
  `// GENERATED by scripts/sync.mjs — do not edit\nwindow.TL = ${JSON.stringify(tl)};\nwindow.GRID = ${JSON.stringify(dataGrid)};\nwindow.BEATS = ${JSON.stringify(beats || {})};\n`);

if (!QUIET) {
  const src = grid ? `grid.json (${Object.keys(grid.cues || {}).length} cues)` : storyboard && sceneIds.length ? `storyboard estimates (${sceneIds.length} scenes, no narration grid yet)` : 'none';
  console.log(`time: seconds · duration ${duration}s @ ${fps} fps · formats ${formats.join(', ')} · cue grid: ${src}${beats ? ' · beat grid: yes' : ''}`);
  for (const [k, t] of Object.entries(marks).sort((a, b) => a[1] - b[1])) console.log(`  ${t.toFixed(3).padStart(8)}s  ${k}`);
  console.log(keepGridPlan ? 'cues.json: kept the grid.py plan (timeline declares no sfx) · film/data.js written' : `cues.json: ${sfx.length} sfx cues · film/data.js written`);
}
for (const [k, t] of late) console.warn(`sync: warning: mark "${k}" is at ${t.toFixed(2)}s, outside the film (0-${duration}s)`);
