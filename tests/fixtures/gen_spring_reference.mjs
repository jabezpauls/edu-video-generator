// Regenerates spring_reference.json: the unit step response of each preset, evaluated with an
// independent closed-form damped-oscillator implementation. Both springs.ts and springs.py are
// tested against that file, so the three stay in lockstep.
//   node tests/fixtures/gen_spring_reference.mjs
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const PRESETS = {
  snappy: { response: 0.22, damping: 0.8 },
  default: { response: 0.4, damping: 0.86 },
  heavy: { response: 0.5, damping: 1.0 },
  playful: { response: 0.5, damping: 0.45 },
};

function step(tau, { response, damping: z }) {
  if (!(tau > 0)) return 0;
  const w = (2 * Math.PI) / response;
  if (z < 1) {
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * tau) * (Math.cos(wd * tau) + ((z * w) / wd) * Math.sin(wd * tau));
  }
  if (z === 1) return 1 - Math.exp(-w * tau) * (1 + w * tau);
  const wd = w * Math.sqrt(z * z - 1);
  return 1 - Math.exp(-z * w * tau) * (Math.cosh(wd * tau) + ((z * w) / wd) * Math.sinh(wd * tau));
}

function settle(p, eps = 0.01) {
  let last = 0;
  for (let tau = 0; tau < 20 * p.response; tau += 0.001) {
    if (Math.abs(1 - step(tau, p)) >= eps) last = tau;
  }
  return last;
}

const out = { eps: 0.01, taus: [], presets: {} };
for (let i = -2; i <= 100; i++) out.taus.push(+(i * 0.025).toFixed(3));
for (const [name, p] of Object.entries(PRESETS)) {
  out.presets[name] = {
    ...p,
    settle: settle(p),
    step: out.taus.map((t) => step(t, p)),
  };
}
const file = join(dirname(fileURLToPath(import.meta.url)), 'spring_reference.json');
writeFileSync(file, JSON.stringify(out) + '\n');
console.log('wrote', file);
