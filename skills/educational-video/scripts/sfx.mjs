#!/usr/bin/env node
// Synthesize lesson sound effects from a cue list -> <project>/audio/sfx.wav
// (48 kHz stereo, 32-bit float). No samples, no dependencies.
//
//   node sfx.mjs [project-dir] [--cues cues.json] [--out audio/sfx.wav]
//
// cues.json is written by `grid.py cues` (Manim / Remotion) or by the motion engine's sync step:
//   { "sr": 48000, "duration": 92.4, "cues": [{ "t": 3.21, "type": "pop", "gain": 0.7, "pitch": 1, "pan": 0 }] }
// Sounds (an educational palette, kept short and soft so they never compete with the voice):
//   pop      something appears: sine glide 820 -> 1720 Hz + soft tick
//   click    a highlight or emphasis: 1 ms HP noise tick + 2.3 kHz blip + 520 Hz body
//   tick     typing / stepping: quieter, shorter click
//   whoosh   a transition: band-passed noise sweeping up, PEAKING at the cue time, panned L -> R
//   chime    the "aha" or a result: two-partial bell with a long, soft decay
//   thump    an impact or the final answer landing: 95 -> 42 Hz sine drop, ~0.5 s
// Cue fields: t (s), type, gain (0.8), pitch (1 = nominal), pan (-1..1). Unknown types are an error.
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const opt = (name, dflt) => { const i = argv.indexOf(name); if (i < 0) return dflt; const v = argv[i + 1]; argv.splice(i, 2); return v; };
const cuesFile = opt('--cues', 'cues.json');
const outFile = opt('--out', path.join('audio', 'sfx.wav'));
const projectDir = argv[0] || '.';
const abs = (p) => (path.isAbsolute(p) ? p : path.join(projectDir, p));

const { sr: SR = 48000, duration, cues } = JSON.parse(fs.readFileSync(abs(cuesFile), 'utf8'));
const N = Math.round(SR * duration);
const L = new Float32Array(N), R = new Float32Array(N);
const mulberry32 = (a) => () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const TAU = Math.PI * 2;

// one-pole high-pass / low-pass on a Float32Array, in place
const hp = (x, fc) => { const a = Math.exp(-TAU * fc / SR); let yp = 0, xp = 0; for (let i = 0; i < x.length; i++) { const y = a * (yp + x[i] - xp); xp = x[i]; yp = y; x[i] = y; } return x; };
const lp = (x, fc) => { const a = 1 - Math.exp(-TAU * fc / SR); let z = 0; for (let i = 0; i < x.length; i++) { z += a * (x[i] - z); x[i] = z; } return x; };
const noise = (n, seed) => { const r = mulberry32(seed); const x = new Float32Array(n); for (let i = 0; i < n; i++) x[i] = r() * 2 - 1; return x; };
// Chamberlin state-variable band-pass with a per-sample centre frequency
function sweepBP(nz, fcOf, q = 0.55) {
  const x = new Float32Array(nz.length); let lo = 0, band = 0;
  for (let i = 0; i < nz.length; i++) {
    const f = 2 * Math.sin(Math.PI * Math.min(fcOf(i / SR), SR / 6) / SR);
    lo += f * band; const hi = nz[i] - lo - q * band; band += f * hi; x[i] = band;
  }
  return x;
}

function click(p, seed, g = 1, len = 0.06) {
  const n = Math.round(len * SR), x = new Float32Array(n), nz = hp(hp(noise(n, seed), 3500), 3500);
  for (let i = 0; i < n; i++) { const t = i / SR; x[i] = (nz[i] * Math.exp(-t * 2600) * 0.9 + Math.sin(TAU * 2300 * p * t) * Math.exp(-t * 190) * 0.45 + Math.sin(TAU * 520 * p * t) * Math.exp(-t * 110) * 0.55) * g; }
  return { x, lead: 0 };
}
const tick = (p, seed) => click(p * 1.25, seed, 0.55, 0.035);
function pop(p, seed) {
  const n = Math.round(0.1 * SR), x = new Float32Array(n), nz = hp(noise(n, seed), 5000); let ph = 0;
  for (let i = 0; i < n; i++) { const t = i / SR, f = (820 + 900 * (1 - Math.exp(-t * 60))) * p; ph += TAU * f / SR; x[i] = Math.sin(ph) * Math.exp(-t * 42) * Math.min(1, t / 0.002) * 0.8 + nz[i] * Math.exp(-t * 3000) * 0.35; }
  return { x, lead: 0 };
}
function thump(p, seed) {
  const n = Math.round(0.6 * SR), x = new Float32Array(n), nz = lp(noise(n, seed), 900); let ph = 0;
  for (let i = 0; i < n; i++) { const t = i / SR, f = (42 + 53 * Math.exp(-t * 22)) * p; ph += TAU * f / SR; x[i] = Math.tanh((Math.sin(ph) * Math.exp(-t * 7) + nz[i] * Math.exp(-t * 60) * 0.6) * 1.6); }
  return { x, lead: 0 };
}
function whoosh(p, seed) {   // 0.30 s build, 0.14 s release; peaks exactly on the cue
  const pre = 0.30, post = 0.14, n = Math.round((pre + post) * SR);
  const bp = sweepBP(noise(n, seed), (t) => (350 + 6500 * Math.min(1, t / pre) ** 2) * p);
  for (let i = 0; i < n; i++) { const t = i / SR, u = Math.min(1, t / pre); bp[i] *= (t < pre ? Math.pow(u, 2.2) : Math.exp(-(t - pre) * 24)) * 0.62; }
  return { x: bp, lead: pre, stereo: true };
}
function chime(p, seed) {   // E6 bell with a fifth and a slightly inharmonic shimmer, ~1.1 s
  const n = Math.round(1.1 * SR), x = new Float32Array(n), f0 = 1318.5 * p;
  for (let i = 0; i < n; i++) {
    const t = i / SR, att = Math.min(1, t / 0.003);
    x[i] = att * (Math.sin(TAU * f0 * t) * Math.exp(-t * 4.2) * 0.55
      + Math.sin(TAU * f0 * 1.5 * t) * Math.exp(-t * 5.5) * 0.25
      + Math.sin(TAU * f0 * 2.76 * t) * Math.exp(-t * 11) * 0.12);
  }
  return { x, lead: 0 };
}
const SYN = { click, tick, pop, thump, whoosh, chime };

cues.forEach((c, k) => {
  if (!SYN[c.type]) throw new Error(`unknown sfx type "${c.type}" (have: ${Object.keys(SYN).join(', ')})`);
  const { x, lead, stereo } = SYN[c.type](c.pitch ?? 1, 9001 + k * 131);
  const start = Math.round((c.t - lead) * SR), g = c.gain ?? 0.8;
  for (let i = 0; i < x.length; i++) {
    const j = start + i; if (j < 0 || j >= N) continue;
    const pan = stereo ? -0.7 + 1.4 * (i / x.length) : (c.pan ?? 0);   // whoosh travels across the field
    L[j] += x[i] * g * Math.sqrt(0.5 * (1 - pan)) * 1.2;
    R[j] += x[i] * g * Math.sqrt(0.5 * (1 + pan)) * 1.2;
  }
});

function wav(path, chans) {   // 32-bit float WAV
  const n = chans[0].length, nc = chans.length, data = Buffer.alloc(n * nc * 4), h = Buffer.alloc(44);
  for (let i = 0; i < n; i++) for (let c = 0; c < nc; c++) data.writeFloatLE(chans[c][i], (i * nc + c) * 4);
  h.write('RIFF', 0); h.writeUInt32LE(36 + data.length, 4); h.write('WAVE', 8); h.write('fmt ', 12); h.writeUInt32LE(16, 16);
  h.writeUInt16LE(3, 20); h.writeUInt16LE(nc, 22); h.writeUInt32LE(SR, 24); h.writeUInt32LE(SR * nc * 4, 28); h.writeUInt16LE(nc * 4, 32); h.writeUInt16LE(32, 34);
  h.write('data', 36); h.writeUInt32LE(data.length, 40); fs.writeFileSync(path, Buffer.concat([h, data]));
}
fs.mkdirSync(path.dirname(abs(outFile)), { recursive: true });
wav(abs(outFile), [L, R]);
let pk = 0; for (let i = 0; i < N; i++) pk = Math.max(pk, Math.abs(L[i]), Math.abs(R[i]));
console.log(`${outFile}  ${cues.length} cues  ${duration}s  peak ${(20 * Math.log10(pk + 1e-12)).toFixed(1)} dBFS`);
