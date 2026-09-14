// Diagrams for algorithms and data structures: nodes, edges, array cells, pointers, labels.
//
//   const d = EDU.diagram(root, {
//     x: 140, y: 300, w: 1000, h: 500,                                   // the box; everything below is relative to it
//     nodes: [{ id: 'a', label: '8', x: 200, y: 100, shape: 'circle' | 'rect' | 'cell', size: 100, at: 'n1',
//               tones: [['visit', 'hi'], ['done', 'accent']],           // colour states over time, each a spring
//               moves: [['shift', { x: 400, y: 100 }]], texts: [['upd', '9']] }],
//     edges: [{ from: 'a', to: 'b', at: 'e1', directed: true, label: 'w=3', tones: [['visit', 'accent']] }],
//     pointers: [{ label: 'lo', stops: [['p0', 'a'], ['p1', 'b']], side: 'below', color: 'hi', lane: 0 }],
//     labels: [{ text: 'index 0', x: 100, y: 240, at: 'n1', size: 26, color: 'ink2' }],
//   });
//   ...in the scene's run(t):  d.run(t);
//
// Tones: ink (default), hi (the thing being looked at), accent (the answer), dim (left behind: fades to a third).
// Pieces enter with a spring pop, never a fade alone. Moves keep velocity when retargeted (like every other trk).
// Helpers build the usual structures: EDU.diagram.array(...) (cells, index labels, pointers, swaps) and
// EDU.diagram.tree(...) (a tree from { id, kids }). Both return the same object with .run(t).
(() => {
  const C = window.C, E = window.EDU, L = window.Layout, K = window.Color;
  const { put, reg, el, at, sp, spHit, trk, trkObj, clamp, lerp } = C;

  // what each tone does to a node
  const TONE = {
    ink: { bg: 'card', fg: 'ink', ring: ['ink', 16] },
    hi: { bg: ['hi', 14, 'card'], fg: 'hi', ring: ['hi', 100] },
    accent: { bg: 'accent', fg: '#ffffff', ring: ['accent', 100] },
  };
  const paint = (spec, t, tones) => {
    let bg = E.tone('card'), fg = E.tone('ink'), ring = E.mix('ink', 'transparent', 16), dimW = 0;
    for (const [when, name] of tones || []) {
      const p = sp(t, when, 'snappy');
      if (p < 0.001) continue;
      if (name === 'dim') { dimW = lerp(dimW, 1, p); continue; }
      const d = TONE[name]; if (!d) throw new Error(`diagram: unknown tone "${name}" (use ink, hi, accent, dim)`);
      dimW = lerp(dimW, 0, p);
      const bgv = Array.isArray(d.bg) ? E.mix(d.bg[0], d.bg[2], d.bg[1]) : E.tone(d.bg);
      bg = E.mix(bgv, bg, p * 100); fg = E.mix(d.fg, fg, p * 100);
      ring = E.mix(Array.isArray(d.ring) ? E.mix(d.ring[0], 'transparent', d.ring[1]) : d.ring, ring, p * 100);
    }
    return { bg, fg, ring, dim: dimW };
  };

  function diagram(parent, o = {}) {
    const W = o.w, H = o.h;
    const box = el('div', { class: 'abs', style: `left:${o.x || 0}px;top:${o.y || 0}px;width:${W}px;height:${H}px` }, parent);
    reg(box);
    const cv = el('canvas', { width: W, height: H, style: `position:absolute;left:0;top:0;width:${W}px;height:${H}px` }, box);
    const g = cv.getContext('2d');

    const nodes = new Map();
    for (const n of o.nodes || []) {
      const shape = n.shape || 'circle', size = n.size || 96, w = n.w || size, h = n.h || size;
      const radius = shape === 'circle' ? '50%' : `${Math.min(w, h) * (shape === 'cell' ? 0.16 : 0.22)}px`;
      const label = n.label == null ? '' : String(n.label);
      const fs = n.fontSize || Math.round(Math.min(w, h) * 0.4 * (label.length > 3 ? 3 / label.length + 0.15 : 1));
      const e = el('div', { class: 'dnode', style: `width:${w}px;height:${h}px;border-radius:${radius};font-size:${fs}px` }, box, label);
      reg(e, { o: 0 });
      nodes.set(n.id, { ...n, shape, w, h, el: e, texts: (n.texts || []).map(([a, b]) => [a, b]), label });
    }
    const home = (id) => { const n = nodes.get(id); if (!n) throw new Error(`diagram: unknown node "${id}"`); return n; };
    const posOf = (n, t) => {
      const keys = [[0, { x: n.x, y: n.y }], ...(n.moves || []).map(([w, p, pr]) => [w, p, pr])];
      const p = trkObj(t, keys);
      let arc = 0;
      for (const [w, , pr, a] of n.moves || []) if (a) { const k = sp(t, w, pr || 'default'); arc += a * 4 * k * (1 - k); }
      return { x: p.x, y: p.y + arc };
    };
    const edges = (o.edges || []).map((e) => ({ ...e, from: home(e.from), to: home(e.to) }));

    const ptrs = (o.pointers || []).map((p) => {
      const fs = p.size || Math.round((o.pointerSize || 34));
      const tri = fs * 0.55, hgt = tri + fs * 1.25, wd = fs * 3;
      const root = el('div', { class: 'dlabel', style: `width:${wd}px;height:${hgt}px;font-size:${fs}px;color:${E.tone(p.color || 'hi')}` }, box);
      const side = p.side || 'below';
      const triEl = el('div', { style: `position:absolute;left:${wd / 2 - tri * 0.6}px;width:${tri * 1.2}px;height:${tri}px;background:currentColor;` +
        (side === 'below' ? `top:0;clip-path:polygon(50% 0,0 100%,100% 100%)` : `bottom:0;clip-path:polygon(50% 100%,0 0,100% 0)`) }, root);
      const txt = el('div', { style: `position:absolute;left:0;width:${wd}px;text-align:center;${side === 'below' ? `top:${tri}px` : `top:0`}` }, root, p.label);
      void triEl; void txt;
      reg(root, { o: 0 });
      const target = (s) => (typeof s === 'string' ? (() => { const n = home(s); return { x: n.x, y: n.y, r: n.h / 2 }; })() : { r: 0, ...s });
      return { ...p, root, side, hgt, wd, stops: p.stops.map(([w, s, pr]) => [w, target(s), pr]) };
    });

    const labels = (o.labels || []).map((l) => {
      const fs = l.size || 26;
      const e = el('div', { class: 'dlabel', style: `font-size:${fs}px;color:${E.tone(l.color || 'ink2')};width:${l.w || fs * 8}px;text-align:${l.align || 'center'}` }, box, l.text);
      reg(e, { o: 0 });
      return { ...l, el: e, ww: l.w || fs * 8 };
    });

    let pal = null;
    function run(t) {
      if (!pal) pal = E.palette();
      // nodes
      const cur = new Map();
      for (const n of nodes.values()) {
        const p = posOf(n, t), a = n.at == null ? 0 : n.at, enter = spHit(t, a, 'snappy');
        cur.set(n, p);
        const st = paint(n, t, n.tones);
        const pop = n.texts.length ? (() => { let k = 0; for (const [w] of n.texts) k = Math.max(k, 4 * sp(t, w, 'snappy') * (1 - sp(t, w, 'snappy'))); return k; })() : 0;
        const props = { o: enter > 0.001 ? clamp(enter) * (1 - 0.68 * st.dim) : 0, x: p.x - n.w / 2, y: p.y - n.h / 2 + (1 - enter) * n.h * 0.25, s: (0.8 + 0.2 * enter) * (1 + 0.12 * pop),
          css: { background: st.bg, color: st.fg, boxShadow: n.shape === 'cell' ? `0 0 0 3px ${st.ring}, 0 14px 30px -14px rgba(0,0,0,.25)` : `0 0 0 4px ${st.ring}` } };
        if (n.texts.length) { let s = n.label; for (const [w, x] of n.texts) if (t >= at(w)) s = x; props.text = s; }
        put(n.el, props);
      }
      // edges
      g.clearRect(0, 0, W, H);
      g.lineCap = 'round';
      for (const e of edges) {
        const p = E.draw(t, e.at, e.dur ?? 0.5);
        if (p < 0.001) continue;
        const A = cur.get(e.from), B = cur.get(e.to);
        const ea = L.exit(e.from.shape, e.from.w, e.from.h, B.x - A.x, B.y - A.y), eb = L.exit(e.to.shape, e.to.w, e.to.h, A.x - B.x, A.y - B.y);
        const gap = (e.gap ?? 6);
        const d = Math.hypot(B.x - A.x, B.y - A.y) || 1, ux = (B.x - A.x) / d, uy = (B.y - A.y) / d;
        const x0 = A.x + ea.x + ux * gap, y0 = A.y + ea.y + uy * gap, x1 = B.x + eb.x - ux * gap, y1 = B.y + eb.y - uy * gap;
        let c = K.parse(E.canvasColor(e.color || 'ink2'));
        for (const [w, name] of e.tones || []) c = K.lerp(c, K.parse(E.canvasColor(name)), clamp(sp(t, w, 'snappy')));
        const width = e.width || 5, q = clamp(p);
        const tx = x0 + (x1 - x0) * q, ty = y0 + (y1 - y0) * q;
        g.strokeStyle = K.css(c); g.fillStyle = K.css(c); g.lineWidth = width;
        g.beginPath(); g.moveTo(x0, y0); g.lineTo(e.directed ? tx - ux * width * 2 * clamp(q * 3) : tx, e.directed ? ty - uy * width * 2 * clamp(q * 3) : ty); g.stroke();
        if (e.directed) {
          const hs = width * 3.4 * clamp(q * 3);
          g.beginPath(); g.moveTo(tx, ty); g.lineTo(tx - ux * hs - uy * hs * 0.5, ty - uy * hs + ux * hs * 0.5); g.lineTo(tx - ux * hs + uy * hs * 0.5, ty - uy * hs - ux * hs * 0.5); g.closePath(); g.fill();
        }
        if (e.label && q > 0.9) {
          const fs = e.size || 28; g.font = `600 ${fs}px ${pal.mono}`; g.textAlign = 'center'; g.textBaseline = 'middle';
          const mx = (x0 + x1) / 2 - uy * fs * 0.9, my = (y0 + y1) / 2 + ux * fs * 0.9;
          g.globalAlpha = clamp((q - 0.9) / 0.1); g.fillStyle = K.css(c); g.fillText(e.label, mx, my); g.globalAlpha = 1;
        }
      }
      // pointers glide between their stops
      for (const p of ptrs) {
        const k0 = p.stops[0][0], on = spHit(t, k0, 'snappy');
        const sign = p.side === 'below' ? 1 : -1, lane = (p.lane || 0) * (p.hgt + 6) * sign;
        const gap = 10;
        const xs = trk(t, p.stops.map(([w, s, pr]) => [w, s.x, pr || 'default'])), ys = trk(t, p.stops.map(([w, s, pr]) => [w, s.y + sign * (s.r + gap), pr || 'default']));
        const top = p.side === 'below' ? ys + lane : ys + lane - p.hgt;
        put(p.root, { o: on > 0.001 ? clamp(on) : 0, x: xs - p.wd / 2, y: top + (1 - on) * sign * 14, s: 0.85 + 0.15 * on });
      }
      for (const l of labels) {
        const on = spHit(t, l.at ?? 0, 'snappy');
        put(l.el, { o: on > 0.001 ? clamp(on) : 0, x: l.x - (l.align === 'left' ? 0 : l.align === 'right' ? l.ww : l.ww / 2), y: l.y + (1 - on) * 12 });
      }
    }
    return { run, box, nodes };
  }

  // ---------------------------------------------------------------- array: cells in slots, pointers, swaps
  /**
   * EDU.diagram.array(parent, {
   *   values: [2, 5, 8], x, y, w, cell: 150, cols, at: 'arr', stagger: 0.07, indices: true,
   *   pointers: [{ label: 'lo', stops: [['p1', 0], ['p2', 3]], side: 'below', color: 'hi', lane: 0 }],   // stops name SLOTS
   *   swaps: [{ at: 'sw1', i: 0, j: 2, arc: 60 }],                                   // the cells in slots i and j trade places
   *   tones: [{ at: 'look1', cells: [3], tone: 'hi' }],                               // cells are the values' original indices
   * })
   */
  function array(parent, o = {}) {
    const n = o.values.length;
    const cellK = o.cell || 140;
    // rows of cells need room for the index labels and pointers that hang under each row
    const hang = (o.indices === false ? 0 : 0.5) + (o.pointers && o.pointers.length ? 0.7 + 0.5 * Math.max(0, ...o.pointers.map((p) => p.lane || 0)) : 0);
    const g = L.grid(n, { w: o.w, cell: cellK, cols: o.cols, gap: o.gap, rowGap: o.rowGap ?? (o.cols && o.cols < n ? cellK * Math.min(0.2 + hang, 1.9) : undefined) });
    const above = (o.pointers || []).some((p) => p.side === 'above');
    const top = o.top ?? g.cell * (above ? 0.6 : 0.2), left = 0;
    const slot = g.pos.map((p) => ({ x: p.x + left, y: p.y + top }));
    const tones = o.tones || [];
    // follow the cells through the swaps: which slot does each cell sit in, and when does it move
    const occ = o.values.map((_, i) => i);
    const moves = o.values.map(() => []);
    for (const s of [...(o.swaps || [])].sort((a, b) => at(a.at) - at(b.at))) {
      const a = occ[s.i], b = occ[s.j], arc = s.arc ?? g.cell * 0.55;
      moves[a].push([s.at, slot[s.j], s.preset || 'default', -arc]); moves[b].push([s.at, slot[s.i], s.preset || 'default', arc]);
      occ[s.i] = b; occ[s.j] = a;
    }
    const nodes = o.values.map((v, i) => ({
      id: `c${i}`, label: v, x: slot[i].x, y: slot[i].y, shape: 'cell', size: g.cell, at: C.at(o.at ?? 0) + i * (o.stagger ?? 0.07),
      moves: moves[i], tones: tones.filter((t) => (t.cells || []).includes(i)).map((t) => [t.at, t.tone]),
      texts: (o.texts || []).filter((t) => t.cell === i).map((t) => [t.at, t.text]),
    }));
    const labels = o.indices === false ? [] : slot.map((p, i) => ({ text: String(i), x: p.x, y: p.y + g.cell * 0.62, size: Math.max(22, g.cell * 0.22), color: 'ink2', w: g.cell, at: C.at(o.at ?? 0) + i * (o.stagger ?? 0.07) + 0.1 }));
    const pointers = (o.pointers || []).map((p) => ({ ...p, size: p.size || Math.max(28, g.cell * 0.26),
      stops: p.stops.map(([w, idx, pr]) => [w, { x: slot[idx].x, y: slot[idx].y, r: g.cell / 2 + (o.indices === false || p.side === 'above' ? 0 : g.cell * 0.42) }, pr]) }));
    const d = diagram(parent, { x: o.x, y: o.y, w: o.w, h: o.h ?? g.height + top + g.cell * (o.below ?? 2.2), nodes, labels, pointers, pointerSize: g.cell * 0.26 });
    d.slot = slot; d.cell = g.cell; d.height = g.height;
    return d;
  }

  // ---------------------------------------------------------------- tree
  /**
   * EDU.diagram.tree(parent, { tree: { id, kids }, x, y, w, h, size: 90, at: 'tree', stagger: 0.35,
   *   labels: { id: 'text' }, reveal: { id: when }, tones: { id: [[when, 'hi']] }, pointers: [...stops name node ids] })
   * Nodes appear parent first, one level every `stagger` seconds unless `reveal` says otherwise; edges draw with the child.
   */
  function tree(parent, o = {}) {
    const lay = L.tree(o.tree), size = o.size || 90, W = o.w, H = o.h;
    const nodes = [], edges = [];
    const base = C.at(o.at ?? 0);
    for (const r of lay.nodes) {
      const when = o.reveal && o.reveal[r.id] != null ? o.reveal[r.id] : base + r.depth * (o.stagger ?? 0.35);
      nodes.push({ id: r.id, label: (o.labels && o.labels[r.id]) ?? r.id, x: size / 2 + r.ux * (W - size), y: size / 2 + r.uy * (H - size), size, shape: o.shape || 'circle',
        at: when, tones: (o.tones && o.tones[r.id]) || [] });
      if (r.parent != null) edges.push({ from: r.parent, to: r.id, at: when, dur: 0.45, directed: o.directed, color: 'ink2', tones: (o.edgeTones && o.edgeTones[`${r.parent}>${r.id}`]) || [] });
    }
    return diagram(parent, { x: o.x, y: o.y, w: W, h: H, nodes, edges, pointers: o.pointers, pointerSize: o.pointerSize });
  }

  diagram.array = array; diagram.tree = tree;
  E.diagram = diagram;
})();
