// Pure planning for step-by-step equations: which pieces of one step are the same pieces in the next (they glide
// instead of leaving and re-entering), and when every piece enters and exits. No DOM; loads as a classic <script>
// (window.TermPlan) or through require() for the unit tests.
//
// A unit is one animated piece of a rendered equation: { kind: 'term' | 'glue', id?, html }.
//   term  a \term{id}{...} group the author named
//   glue  everything else at the top level ("=", "+", brackets): it enters with its neighbouring term
// Two units are the same piece when kind, id (terms) and rendered html all match; the nth repeat of a piece matches the
// nth repeat in the other step. Same id with different html is NOT the same piece: it leaves and the new one enters.
(function (root, factory) {
  const P = factory();
  if (typeof module === 'object' && module.exports) module.exports = P;
  else root.TermPlan = P;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const keyOf = (u) => (u.kind === 'term' ? `t:${u.id}` : `g:${u.html}`);

  /** For every unit of `next`, the index of its twin in `prev`, or -1. */
  function match(prev, next) {
    const seen = new Map();
    const index = new Map();      // `${key}#${n}` -> index in prev
    prev.forEach((u, i) => {
      const k = keyOf(u), n = seen.get(k) || 0; seen.set(k, n + 1);
      if (u.html != null) index.set(`${k}#${n}#${u.html}`, i);
    });
    const used = new Map();
    return next.map((u) => {
      const k = keyOf(u), n = used.get(k) || 0; used.set(k, n + 1);
      const i = index.get(`${k}#${n}#${u.html}`);
      return i == null ? -1 : i;
    });
  }

  /**
   * steps: [{ units, at, reveal? }] with `at` already in seconds and reveal { termId: seconds } (seconds too).
   * opts: { stagger = 0.07, until = Infinity (when the last step leaves), exitStagger = 0.03 }
   * returns per step, per unit: { from, to, enter, exit }
   *   from  index of the twin in the previous step (the unit glides from there), else -1
   *   to    index of the twin in the next step, else -1
   *   enter seconds the unit appears (null when it arrives by gliding)
   *   exit  seconds it leaves (null when it glides on to its twin)
   */
  function plan(steps, opts = {}) {
    const stagger = opts.stagger ?? 0.07, exitStagger = opts.exitStagger ?? 0.03, until = opts.until ?? Infinity;
    const out = steps.map((s) => s.units.map(() => ({ from: -1, to: -1, enter: null, exit: null })));
    for (let i = 1; i < steps.length; i++) {
      const m = match(steps[i - 1].units, steps[i].units);
      m.forEach((j, k) => { if (j >= 0) { out[i][k].from = j; out[i - 1][j].to = k; } });
    }
    steps.forEach((s, i) => {
      const at = s.at, reveal = s.reveal || {};
      let order = 0;
      const when = s.units.map((u, k) => {
        if (out[i][k].from >= 0) return null;
        if (u.kind !== 'term') return undefined;           // glue: decided from its neighbours below
        return reveal[u.id] != null ? reveal[u.id] : at + stagger * order++;
      });
      const termTime = (k) => (out[i][k].from >= 0 ? at : when[k]);
      s.units.forEach((u, k) => {
        const o = out[i][k];
        if (o.from >= 0) return;
        if (u.kind === 'term') { o.enter = when[k]; return; }
        let t = null;
        for (let n = k + 1; n < s.units.length && t == null; n++) if (s.units[n].kind === 'term') t = termTime(n);
        for (let n = k - 1; n >= 0 && t == null; n--) if (s.units[n].kind === 'term') t = termTime(n);
        o.enter = t == null ? at + stagger * order++ : t;
      });
      const leave = i + 1 < steps.length ? steps[i + 1].at : until;
      let e = 0;
      s.units.forEach((u, k) => { const o = out[i][k]; if (o.to < 0) o.exit = leave + exitStagger * e++; });
    });
    return out;
  }

  return { match, plan };
});
