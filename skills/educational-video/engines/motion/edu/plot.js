// Plots: axes, grid and function curves drawn on a canvas, over time.
//
//   const p = EDU.plot(root, {
//     x: 140, y: 200, w: 1100, h: 640, xr: [0, 16], yr: [0, 5], xLabel: 'n', yLabel: 'looks', size: 30,
//     axes: { at: 'axes', dur: 0.9 },
//     curves: [{ fn: (n) => Math.log2(n), from: 1, at: 'curve', dur: 1.8, color: 'accent', width: 8, label: 'log₂ n' }],
//     points: [{ x: 8, y: 3, at: 'pt', label: '8 items: 3 looks', color: 'hi' }],
//     segments: [{ from: [8, 0], to: [8, 3], at: 'pt', dash: [10, 10] }],                       // guides, secants, tangents
//     markers: [{ curve: 0, stops: [['m1', 2], ['m2', 8], ['m3', 16]], drop: true, label: (x, y) => `n = ${x}` }],
//   });
//   ...in the scene's run(t):  p.run(t);
//
// Everything is a function of t: a curve is sampled once per frame and truncated to the fraction drawn so far, the pen
// moves at constant speed along it. `dur` is when the draw is (nearly) finished; a draw is a critically damped spring,
// so it eases out and never has a visible end tick. Colours are look tokens (accent, hi, ink, ink2) or any css colour.
// p.toStage(x, y) turns data coordinates into stage pixels, so DOM labels and equations can be pinned to the plot.
(() => {
  const C = window.C, E = window.EDU, PM = window.PlotMath;
  const { put, reg, el, at, spHit, trk, clamp } = C;

  function plot(parent, o = {}) {
    const W = o.w, H = o.h, size = o.size || 28;
    const xr = o.xr || [0, 10], yr = o.yr || [0, 10];
    const ml = size * (o.yLabel ? 3.4 : 2.6), mb = size * 2.2, mt = size * 1.2, mr = size * 1.4;
    const px = { l: ml, t: mt, r: W - mr, b: H - mb };
    const map = { x: (v) => px.l + ((v - xr[0]) / (xr[1] - xr[0])) * (px.r - px.l), y: (v) => px.b - ((v - yr[0]) / (yr[1] - yr[0])) * (px.b - px.t) };
    const box = el('div', { class: 'abs', style: `left:${o.x || 0}px;top:${o.y || 0}px;width:${W}px;height:${H}px` }, parent);
    reg(box, { o: 0 });
    const cv = el('canvas', { width: W, height: H, style: `position:absolute;left:0;top:0;width:${W}px;height:${H}px` }, box);
    const g = cv.getContext('2d');
    const curves = (o.curves || []).map((c) => {
      const a = c.from ?? xr[0], b = c.to ?? xr[1];
      const polys = PM.toPixels(PM.sample(c.fn, a, b, Math.ceil((px.r - px.l) / 1.5), yr), map);
      return { ...c, polys, a, b };
    });
    const tx = PM.ticks(xr[0], xr[1], o.xTicks || Math.max(3, Math.round((px.r - px.l) / (size * 5)))), ty = PM.ticks(yr[0], yr[1], o.yTicks || Math.max(3, Math.round((px.b - px.t) / (size * 4))));
    const ax = o.axes || {}, axAt = ax.at == null ? 0 : at(ax.at), axDur = ax.dur ?? 0.9;
    const ox = clamp(0, xr[0], xr[1]), oy = clamp(0, yr[0], yr[1]);   // axes cross at zero when it is in view
    let style = null;
    const read = () => {
      const cs = getComputedStyle(document.getElementById('stage'));
      const v = (n) => cs.getPropertyValue(n).trim();
      style = { mono: v('--font-mono') || 'monospace', col: { ink: v('--ink'), ink2: v('--ink-2'), accent: v('--accent'), hi: v('--hi'), card: v('--card'), bg: v('--bg') } };
    };
    const col = (n) => style.col[n] || n;

    function run(t) {
      if (!style) read();
      const enter = spHit(t, o.at ?? axAt - 0.15, 'default');
      put(box, { o: enter > 0.001 ? 1 : 0, y: (1 - enter) * size * 0.8 });
      g.clearRect(0, 0, W, H);
      g.lineCap = 'round'; g.lineJoin = 'round';
      const pa = o.axes === false ? 1 : E.draw(t, axAt, axDur);
      g.font = `${size}px ${style.mono}`;
      // grid and ticks
      if (pa > 0.001) {
        g.save();
        g.globalAlpha = clamp(pa);
        g.strokeStyle = col('ink'); g.fillStyle = col('ink2');
        if (o.grid !== false) {
          g.globalAlpha = 0.09 * clamp(pa); g.lineWidth = 2;
          g.beginPath();
          for (const v of tx.values) { g.moveTo(map.x(v), px.t); g.lineTo(map.x(v), px.b); }
          for (const v of ty.values) { g.moveTo(px.l, map.y(v)); g.lineTo(px.r, map.y(v)); }
          g.stroke();
        }
        g.globalAlpha = clamp(pa);
        g.textAlign = 'center'; g.textBaseline = 'top';
        for (const v of tx.values) { if (v === ox && ox !== xr[0]) continue; g.fillText(PM.fmt(v, tx.step), map.x(v), px.b + size * 0.5); }
        g.textAlign = 'right'; g.textBaseline = 'middle';
        for (const v of ty.values) { if (v === oy && oy !== yr[0]) continue; g.fillText(PM.fmt(v, ty.step), px.l - size * 0.5, map.y(v)); }
        // the axes themselves grow from the origin to the arrow ends
        g.lineWidth = Math.max(3, size * 0.12); g.globalAlpha = 1;
        const X0 = map.x(ox), Y0 = map.y(oy);
        g.beginPath(); g.moveTo(px.l, Y0); g.lineTo(px.l + (px.r - px.l) * pa, Y0);
        g.moveTo(X0, px.b); g.lineTo(X0, px.b - (px.b - px.t) * pa); g.stroke();
        if (pa > 0.85) {
          g.globalAlpha = clamp((pa - 0.85) / 0.15); g.fillStyle = col('ink');
          g.textAlign = 'right'; g.textBaseline = 'bottom'; if (o.xLabel) g.fillText(o.xLabel, px.r, Y0 - size * 0.4);
          g.textAlign = 'left'; g.textBaseline = 'top'; if (o.yLabel) g.fillText(o.yLabel, X0 + size * 0.5, px.t - size * 0.3);
        }
        g.restore();
      }
      g.save();
      g.beginPath(); g.rect(px.l - 4, px.t - 8, px.r - px.l + 8, px.b - px.t + 16); g.clip();
      // segments
      for (const s of o.segments || []) {
        const p = E.draw(t, s.at, s.dur ?? 0.6);
        if (p < 0.001) continue;
        const a = [map.x(s.from[0]), map.y(s.from[1])], b = [map.x(s.to[0]), map.y(s.to[1])];
        g.strokeStyle = col(s.color || 'ink2'); g.lineWidth = s.width || Math.max(3, size * 0.12); g.setLineDash(s.dash || []);
        g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p); g.stroke();
      }
      g.setLineDash([]);
      // curves
      for (const c of curves) {
        const p = E.draw(t, c.at, c.dur ?? 1.4);
        if (p < 0.001) continue;
        const { polys, tip } = PM.truncate(c.polys, p);
        g.strokeStyle = col(c.color || 'accent'); g.lineWidth = c.width || Math.max(5, size * 0.28); g.setLineDash(c.dash || []);
        for (const pl of polys) { g.beginPath(); pl.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); }
        g.setLineDash([]);
        if (tip && p < 0.995 && c.pen !== false) { g.fillStyle = col(c.color || 'accent'); g.beginPath(); g.arc(tip[0], tip[1], g.lineWidth * 1.1, 0, Math.PI * 2); g.fill(); }
      }
      g.restore();
      // curve labels, points and markers sit above the clip so they are never cut at the edge
      g.setLineDash([]);
      for (const c of curves) {
        if (!c.label) continue;
        const p = E.draw(t, c.at, c.dur ?? 1.4), a = clamp((p - 0.9) / 0.1);
        if (a <= 0.001) continue;
        const lastPoly = c.polys[c.polys.length - 1]; if (!lastPoly) continue;
        const [x, y] = lastPoly[lastPoly.length - 1];
        g.save(); g.globalAlpha = a; g.fillStyle = col(c.color || 'accent'); g.font = `600 ${size * 1.15}px ${style.mono}`;
        g.textAlign = 'right'; g.textBaseline = 'top'; g.fillText(c.label, Math.min(x, px.r), y + size * 0.8); g.restore();   // below the end: curves that rise leave it clear
      }
      for (const m of o.markers || []) {
        const c = curves[m.curve ?? 0]; if (!c) continue;
        const stops = m.stops.map(([w, v, pr]) => [w, v, pr]);
        const on = spHit(t, stops[0][0], 'snappy'); if (on < 0.001) continue;
        const xv = trk(t, stops), yv = c.fn(xv), X = map.x(xv), Y = map.y(yv);
        g.save(); g.globalAlpha = clamp(on);
        if (m.drop) {
          g.strokeStyle = col(m.color || 'hi'); g.lineWidth = 3; g.setLineDash([8, 8]);
          g.beginPath(); g.moveTo(X, Y); g.lineTo(X, map.y(oy)); g.moveTo(X, Y); g.lineTo(map.x(ox), Y); g.stroke(); g.setLineDash([]);
        }
        g.fillStyle = col('card'); g.strokeStyle = col(m.color || 'hi'); g.lineWidth = Math.max(4, size * 0.16);
        g.beginPath(); g.arc(X, Y, size * 0.42 * (0.6 + 0.4 * on), 0, Math.PI * 2); g.fill(); g.stroke();
        if (m.label) {
          g.fillStyle = col(m.color || 'hi'); g.font = `600 ${size}px ${style.mono}`; g.textAlign = 'left'; g.textBaseline = 'bottom';
          const s = m.label(+xv.toFixed(2), +yv.toFixed(2)), wd = g.measureText(s).width;
          g.fillText(s, Math.min(X + size * 0.7, px.r - wd), Y - size * 0.7);
        }
        g.restore();
      }
      for (const q of o.points || []) {
        const p = spHit(t, q.at, 'snappy'); if (p < 0.001) continue;
        const X = map.x(q.x), Y = map.y(q.y), r = (q.r || size * 0.4) * (0.5 + 0.5 * p);
        g.save(); g.globalAlpha = clamp(p);
        g.fillStyle = col(q.color || 'accent'); g.beginPath(); g.arc(X, Y, r, 0, Math.PI * 2); g.fill();
        if (q.label) {
          g.fillStyle = col('ink'); g.font = `600 ${size}px ${style.mono}`; g.textAlign = q.align || 'left'; g.textBaseline = 'bottom';
          const s = q.label, wd = g.measureText(s).width;
          const lx = q.align === 'right' ? X - size * 0.7 : Math.min(X + size * 0.7, px.r - wd);
          g.fillText(s, lx, Y - size * 0.7);
        }
        g.restore();
      }
    }
    const toStage = (x, y) => ({ x: (o.x || 0) + map.x(x), y: (o.y || 0) + map.y(y) });
    return { run, box, map, toStage, inner: px, curves };
  }
  E.plot = plot;
})();
