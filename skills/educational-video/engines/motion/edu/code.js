// Code: a syntax-highlighted panel with typing on or line-by-line reveal, and a focus band that glides between line
// ranges while everything else dims.
//
//   const k = EDU.code(root, {
//     x: 120, y: 300, w: 1100, size: 40, lang: 'python', numbers: true,
//     code: 'def search(xs, target):\n    lo, hi = 0, len(xs) - 1\n    ...',          // the exact source from the storyboard
//     reveal: { mode: 'type', from: 'code_in', to: 'code_done' },                         // or { mode: 'lines', from, every: 0.4 | at: [whens] }
//     focus: [{ at: 'look1', lines: [3, 4] }, { at: 'look2', lines: [5, 5] }, { at: 'done', lines: null }],   // 1-based, inclusive
//   });
//   ...in the scene's run(t):  k.run(t);
//
// The panel is `w` wide; when the longest line does not fit at `size`, the text size shrinks until it does (the
// returned `size` is what was used). Phone frames have ~30 columns at a readable size: pick a narrower variant of the
// same code for tall frames (shorter names, a comment moved to its own line) rather than letting it shrink.
(() => {
  const C = window.C, E = window.EDU, TK = window.Tokens, M = window.Motion;
  const { put, reg, el, at, spHit, trk, seg, clamp, lerp } = C;

  function code(parent, o = {}) {
    const src = String(o.code ?? '').replace(/\n$/, '').replace(/\t/g, '    ');
    const lines = TK.tokenize(src, o.lang || 'text');
    const cols = Math.max(1, ...lines.map(TK.length));
    const digits = String(lines.length).length, gcols = o.numbers === false ? 0 : digits + 1.4;
    // the size asked for, reduced until the longest line fits the panel width (0.61 em per column, a hair of slack)
    let size = o.size || 40;
    if (o.w) size = Math.min(size, o.w / (0.61 * (cols + gcols) + 1.7));
    const lh = size * (o.lineHeight || 1.55), pad = size * 0.85, gutter = gcols * size * 0.602;
    const w = o.w || Math.ceil(gutter + cols * size * 0.61 + 2 * pad);
    const h = lines.length * lh + 2 * pad;
    const panel = o.panel !== false;
    const rv = { mode: 'none', ...(o.reveal || {}) };
    const dim = o.dim ?? 0.28;

    const box = el('div', { class: 'abs', style: `left:${o.x || 0}px;top:${o.y || 0}px;width:${w}px;height:${h}px;font-size:${size}px;line-height:${lh}px` }, parent);
    reg(box, { o: 0 });
    if (panel) el('div', { style: `position:absolute;inset:0;border-radius:${size * 0.5}px;background:var(--card);box-shadow:0 2px 6px rgba(0,0,0,.05), 0 30px 80px -20px rgba(0,0,0,.22)` }, box);
    const band = reg(el('div', { style: `position:absolute;left:${pad * 0.5}px;width:${w - pad}px;top:0;height:${lh}px;border-radius:${size * 0.2}px;background:var(--c-line);box-shadow:inset ${size * 0.12}px 0 0 var(--hi)` }, box), { o: 0 });
    const probe = el('span', { class: 'mono', style: 'position:absolute;visibility:hidden;white-space:pre' }, box, 'M'.repeat(40));
    const rows = lines.map((ln, i) => {
      const row = el('div', { class: 'code ln', style: `left:${pad}px;top:${pad + i * lh}px;width:${w - 2 * pad}px;height:${lh}px` }, box);
      if (gutter) el('span', { style: `position:absolute;left:0;width:${gutter - size * 0.9}px;text-align:right;color:color-mix(in srgb, var(--ink-2) 60%, transparent)` }, row, String(i + 1));
      const text = el('span', { style: `position:absolute;left:${gutter}px;top:0` }, row);
      reg(row, { o: 0 }); reg(text);
      return { row, text, ln };
    });
    const caret = reg(el('div', { style: `position:absolute;left:0;top:0;width:${size * 0.12}px;height:${lh * 0.72}px;margin-top:${lh * 0.14}px;background:var(--accent);border-radius:2px` }, box), { o: 0 });

    // character offset of every line in the typed stream (a newline counts as one keystroke)
    const starts = []; let acc = 0;
    for (const ln of lines) { starts.push(acc); acc += TK.length(ln) + 1; }
    const total = acc - 1;
    const rvFrom = rv.from == null ? null : at(rv.from);
    const rowAt = (i) => (Array.isArray(rv.at) ? at(rv.at[i]) : rvFrom + i * (rv.every ?? 0.35));

    const stops = (o.focus || []).map((f) => ({ t: at(f.at), a: f.lines ? f.lines[0] : null, b: f.lines ? f.lines[1] : null }));
    // the band remembers the last range while it fades out
    const held = []; let last = [1, 1];
    for (const s of stops) { if (s.a != null) last = [s.a, s.b]; held.push(last); }
    const ind = stops.map((s, i) => [s.t, held[i][0] - 1, held[i][1]]);
    let charW = null;

    function run(t) {
      if (charW == null) charW = probe.offsetWidth / 40 || size * 0.602;
      const t0 = rvFrom ?? 0;
      const enter = spHit(t, o.at ?? (rvFrom == null ? 0 : t0 - 0.2), 'default');
      put(box, { o: enter > 0.001 ? 1 : 0, y: (1 - enter) * size * 0.9, s: lerp(0.94, 1, enter) });
      const typed = rv.mode === 'type' ? Math.floor(seg(t, rv.from, rv.to ?? rv.from) * total + 1e-6) : total;
      let caretAt = null;
      rows.forEach((r, i) => {
        let a = 1, shift = 0, html = null;
        if (rv.mode === 'type') {
          const n = Math.max(0, Math.min(TK.length(r.ln), typed - starts[i]));
          a = typed >= starts[i] ? 1 : 0;
          html = TK.html(r.ln, n);
          if (typed >= starts[i] && typed <= starts[i] + TK.length(r.ln)) caretAt = { i, n };
        } else if (rv.mode === 'lines') {
          const p = spHit(t, rowAt(i), 'snappy');
          a = p > 0.001 ? 1 : 0; shift = (1 - p) * lh * 0.5;
        }
        // dimming: 1 inside the focused range, `dim` outside; no stops or a cleared focus: everything at 1
        let f = 1;
        if (stops.length) {
          f = trk(t, [[0, 1], ...stops.map((s) => [s.t, s.a == null ? 1 : (i + 1 >= s.a && i + 1 <= s.b ? 1 : 0), 'snappy'])]);
        }
        put(r.row, { o: a * lerp(dim, 1, clamp(f)), y: shift });
        put(r.text, { html: html == null ? TK.html(r.ln) : html });
      });
      // the focus band: stretches toward the next range, then settles; invisible when no focus is set
      if (stops.length) {
        const b = M.indicator(t, [[0, ind[0][1], ind[0][2]], ...ind], { lead: 'snappy', trail: 'default' });
        const on = trk(t, [[0, 0], ...stops.map((s) => [s.t, s.a == null ? 0 : 1, 'snappy'])]);
        put(band, { o: clamp(on) * (enter > 0.5 ? 1 : 0), y: pad + b.start * lh, css: { height: `${(b.size * lh).toFixed(2)}px` } });
      } else put(band, { o: 0 });
      if (caretAt && rv.mode === 'type') {
        const blink = typed < total || Math.floor(t * 2.4) % 2 === 0;
        put(caret, { o: blink && t < (rv.to == null ? Infinity : at(rv.to)) + 1.5 ? 1 : 0, x: pad + gutter + caretAt.n * charW, y: pad + caretAt.i * lh });
      } else put(caret, { o: 0 });
    }
    return { run, box, lines, size, lh, w, h, pad };
  }
  E.code = code;
})();
