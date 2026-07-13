// Time source for the motion engine. Everything on screen is placed in SECONDS; this module turns the names a film
// uses into seconds. A "when" is any of:
//
//   3.25                 seconds from the start of the film
//   'reveal'             a mark from timeline.json (a mark is itself a when: seconds, a cue, or another mark)
//   's03.derivative'     a cue from the cue grid (narration word timings land here; see scripts/sync.mjs)
//   's03.derivative+0.3' any of the above with a signed offset in seconds
//   '@16'                beat 16 of the optional music grid (beats.json); '@16+0.5' works too
//
// Pure functions, no DOM: loads as a classic <script> (window.Time) or via require(), like lib/motion.js.
(function (root, factory) {
  const T = factory();
  if (typeof module === 'object' && module.exports) module.exports = T;
  else root.Time = T;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const NUM = /^[+-]?(\d+\.?\d*|\.\d+)$/;

  /**
   * opts.marks  { name: when }                  names defined by the film (timeline.json)
   * opts.cues   { name: seconds }               the cue grid: sNN.start, sNN.word, sNN.p2, ...
   * opts.beats  { beat?, offset?, beats?: [s] } optional music grid; or opts.bpm for a nominal one
   */
  function makeTime(opts = {}) {
    const marks = opts.marks || {}, cues = opts.cues || {}, B = opts.beats || {};
    const GRID = Array.isArray(B.beats) && B.beats.length > 1 ? B.beats : null;
    const PERIOD = B.beat || 60 / (opts.bpm || 120);
    const B0 = GRID ? GRID[0] : (B.offset || 0);

    /** Beat n (fractions allowed) → seconds: linear between measured beats, nominal period outside them. */
    function beat(n) {
      if (!GRID) return B0 + n * PERIOD;
      if (n <= 0) return GRID[0] + n * PERIOD;
      const i = Math.floor(n), L = GRID.length;
      if (i >= L - 1) return GRID[L - 1] + (n - (L - 1)) * PERIOD;
      return GRID[i] + (n - i) * (GRID[i + 1] - GRID[i]);
    }

    const stack = [];
    function lookup(name) {
      if (Object.prototype.hasOwnProperty.call(marks, name)) {
        if (stack.includes(name)) throw new Error(`time: marks refer to each other in a loop (${[...stack, name].join(' -> ')})`);
        stack.push(name);
        try { return at(marks[name]); } finally { stack.pop(); }
      }
      if (Object.prototype.hasOwnProperty.call(cues, name)) return cues[name];
      return null;
    }

    /** Any "when" → seconds. Throws on a name that is neither a mark nor a cue. */
    function at(x) {
      if (typeof x === 'number') {
        if (!Number.isFinite(x)) throw new Error(`time: not a finite number (${x})`);
        return x;
      }
      if (typeof x !== 'string') throw new Error(`time: cannot place ${JSON.stringify(x)} (expected seconds, a mark or a cue)`);
      const s = x.trim();
      if (NUM.test(s)) return parseFloat(s);
      const whole = lookup(s);
      if (whole != null) return whole;
      const m = s.match(/^(.+?)\s*([+-])\s*(\d*\.?\d+)s?$/);
      if (m) {
        const off = (m[2] === '-' ? -1 : 1) * parseFloat(m[3]);
        const ref = m[1].trim();
        const b = ref.match(/^@(-?\d*\.?\d+)$/);
        if (b) return beat(parseFloat(b[1])) + off;
        const base = lookup(ref);
        if (base != null) return base + off;
      }
      const b = s.match(/^@(-?\d*\.?\d+)$/);
      if (b) return beat(parseFloat(b[1]));
      throw new Error(`time: unknown mark or cue "${s}"${hint(s)}`);
    }

    function hint(s) {
      const names = [...Object.keys(marks), ...Object.keys(cues)];
      const near = names.filter((n) => n.includes(s) || s.includes(n)).slice(0, 4);
      return near.length ? ` (did you mean ${near.map((n) => `"${n}"`).join(', ')}?)` : '';
    }

    /** Every mark resolved to seconds, in definition order. */
    function resolveMarks() {
      const out = {};
      for (const k of Object.keys(marks)) out[k] = at(k);
      return out;
    }

    return { at, beat, resolveMarks, has: (n) => { try { at(n); return true; } catch { return false; } } };
  }

  return { makeTime };
});
