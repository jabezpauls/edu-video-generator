// Equations: KaTeX typesetting (vendored, offline) with per-term reveal, highlight and step-to-step swaps.
//
//   const eq = EDU.equation(root, {
//     x: 140, y: 400, w: 1640, size: 120, align: 'left',
//     steps: [
//       { tex: '\\term{lhs}{x^2} \\term{eq}{=} \\term{rhs}{4}', at: 'eq1', reveal: { lhs: 'eq1', rhs: 'eq1_rhs' } },
//       { tex: '\\term{lhs}{x^2} \\term{eq}{=} \\term{rhs}{2^2}', at: 'eq2' },
//     ],
//     hi: [{ term: 'rhs', from: 'eq1_rhs', to: 'eq2', tone: 'hi' }],
//   });
//   ...in the scene's run(t):  eq.run(t);
//
// \term{id}{tex} names a piece of the equation (ids: letters, digits, dash, underscore). Everything outside a \term at
// the top level ("=", "+", brackets) is glue: it enters with the next term. A piece whose id and typeset result are the
// same in the next step glides to its new place; everything else leaves and the new pieces enter. The author writes the
// real TeX of every step, nothing is generated or paraphrased.
// Limits: a \term inside a fraction or root animates on its own but the fraction bar / root sign belongs to the step and
// shows with it; wrap the whole fraction in a \term when the bar should arrive with its terms.
(() => {
  const C = window.C, E = window.EDU, TP = window.TermPlan;
  const { put, reg, el, sp, spHit, win, at, clamp } = C;

  const render = (tex) => window.katex.renderToString(tex, {
    output: 'html', throwOnError: true, strict: 'ignore', trust: (c) => c.command === '\\htmlClass',
    macros: { '\\term': '\\htmlClass{eq-#1}{#2}' },
  });
  const termId = (e) => { const m = /(?:^|\s)eq-([\w-]+)/.exec(e.getAttribute('class') || ''); return m && /(?:^|\s)enclosing(?:\s|$)/.test(e.getAttribute('class')) ? m[1] : null; };
  const inTerm = (e, root) => { for (let p = e.parentElement; p && p !== root; p = p.parentElement) if (termId(p)) return true; return false; };

  /** The animated pieces of one rendered step, in reading order: [{ el, kind, id, html }]. */
  function collect(box) {
    const units = [];
    const terms = [...box.querySelectorAll('.enclosing')].filter((e) => termId(e) && !inTerm(e, box));
    for (const e of terms) units.push({ el: e, kind: 'term', id: termId(e), html: e.outerHTML });
    for (const base of box.querySelectorAll('.katex-html > .katex-base')) {
      for (const c of base.children) {
        if (c.classList.contains('katex-strut') || termId(c) || c.querySelector('.enclosing')) continue;
        if (!c.textContent && !c.firstElementChild) continue;          // a spacer
        units.push({ el: c, kind: 'glue', id: null, html: c.outerHTML });
      }
    }
    // reading order
    units.sort((a, b) => (a.el.compareDocumentPosition(b.el) & 4 ? -1 : 1));
    return units;
  }

  /** Where a piece sits inside its step's box, from layout that ignores transforms (safe to read on any frame). */
  function offsetIn(e, root) {
    let x = 0, y = 0;
    for (let n = e; n && n !== root; n = n.offsetParent) { x += n.offsetLeft; y += n.offsetTop; }
    return { x, y };
  }

  function equation(parent, o = {}) {
    const size = o.size || 110, w = o.w || C.W - 2 * (o.x || 0), align = o.align || 'left';
    const preset = o.preset || 'snappy', swap = o.swap || 'default', stagger = o.stagger ?? 0.07;
    const steps = (o.steps || [{ tex: o.tex, at: o.at }]).map((s, i) => {
      if (typeof s.tex !== 'string') throw new Error(`equation: step ${i} needs a tex string`);
      const box = el('div', { class: 'abs eq', style: `left:${o.x || 0}px;top:${o.y || 0}px;width:${w}px;font-size:${size}px;` +
        `text-align:${align};white-space:nowrap;color:${E.tone(o.color || 'ink')};transform-origin:${align === 'center' ? '50% 0' : '0 0'}` }, parent, render(s.tex));
      reg(box, { hide: true });
      const units = collect(box);
      for (const u of units) {
        u.el.style.display = 'inline-block'; u.el.style.transformOrigin = '50% 60%';
        reg(u.el, { o: 0 });
      }
      return { ...s, box, units, katex: box.querySelector('.katex') };
    });
    const spec = steps.map((s) => ({ units: s.units.map(({ kind, id, html }) => ({ kind, id, html })), at: at(s.at),
      reveal: Object.fromEntries(Object.entries(s.reveal || {}).map(([k, v]) => [k, at(v)])) }));
    const plan = TP.plan(spec, { stagger, until: o.until == null ? Infinity : at(o.until) });
    // window each step's box is visible in
    const win0 = plan.map((p, i) => Math.min(spec[i].at, ...p.map((u) => (u.enter == null ? Infinity : u.enter))) - 0.1);
    const win1 = plan.map((p, i) => Math.max(spec[i].at, ...p.map((u) => (u.exit == null ? -Infinity : u.exit))) + 0.7);
    const hi = (o.hi || []).map((h) => ({ term: h.term, from: h.from, to: h.to ?? null, tone: h.tone || 'hi', fill: h.fill ?? 0.16, grow: h.grow ?? 0.06 }));
    let M = null;           // measured layout, filled on first run (fonts are loaded by then; offsets ignore transforms)

    function measure() {
      M = steps.map((s) => {
        const nat = s.katex ? s.katex.offsetWidth : w;
        const k = o.fit === false ? 1 : Math.min(1, w / nat);
        return { k, pos: s.units.map((u) => offsetIn(u.el, s.box)) };
      });
    }
    const ox = align === 'center' ? w / 2 : 0;
    const stagePos = (i, k) => ({ x: ox + M[i].k * (M[i].pos[k].x - ox), y: M[i].k * M[i].pos[k].y });

    function run(t) {
      if (!M) measure();
      steps.forEach((s, i) => {
        const live = t >= win0[i] && t < win1[i];
        put(s.box, { hide: !live, s: M[i].k });
        if (!live) return;
        const pSwap = i > 0 ? spHit(t, spec[i].at, swap) : 0;
        const pNext = i + 1 < steps.length ? spHit(t, spec[i + 1].at, swap) : 0;
        s.units.forEach((u, k) => {
          const pl = plan[i][k];
          let a = 1, x = 0, y = 0, sc = 1;
          if (pl.from < 0) {
            const pe = spHit(t, pl.enter, preset);
            a *= pe; y += (1 - pe) * size * 0.3; sc *= 0.9 + 0.1 * pe;
          } else {
            a *= pSwap >= 0.5 ? 1 : 0;
            const from = stagePos(i - 1, pl.from), here = stagePos(i, k);
            x += ((from.x - here.x) / M[i].k) * (1 - pSwap); y += ((from.y - here.y) / M[i].k) * (1 - pSwap);
          }
          if (pl.to < 0) {
            const px = pl.exit === Infinity ? 0 : sp(t, pl.exit, preset);
            a *= 1 - px; y -= px * size * 0.35; sc *= 1 - 0.08 * px;
          } else {
            a *= pNext < 0.5 ? 1 : 0;
            const here = stagePos(i, k), to = stagePos(i + 1, pl.to);
            x += ((to.x - here.x) / M[i].k) * pNext; y += ((to.y - here.y) / M[i].k) * pNext;
          }
          const p = { o: a > 0.001 ? clamp(a) : 0, x, y, s: sc };
          if (u.id) {
            let best = null;
            for (const h of hi) if (h.term === u.id) { const v = clamp(win(t, h.from, h.to, 'snappy', 'snappy')); if (v > 0.002 && (!best || v > best.v)) best = { v, h }; }
            if (best) {
              p.s *= 1 + best.h.grow * best.v;
              p.css = { color: E.mix(best.h.tone, o.color || 'ink', best.v * 100), background: E.mix(best.h.tone, 'transparent', best.v * best.h.fill * 100),
                boxShadow: `0 0 0 0.1em ${E.mix(best.h.tone, 'transparent', best.v * best.h.fill * 100)}` };
            }
          }
          put(u.el, p);
        });
      });
    }
    return { run, steps, plan, size };
  }

  E.equation = equation;
})();
