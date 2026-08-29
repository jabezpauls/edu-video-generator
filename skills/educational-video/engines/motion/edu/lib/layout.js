// Pure layouts for diagrams: rows and grids of cells, trees, circles. Positions are centres in the box you give.
// Loads as a classic <script> (window.Layout) or through require().
(function (root, factory) {
  const L = factory();
  if (typeof module === 'object' && module.exports) module.exports = L;
  else root.Layout = L;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /**
   * n cells in `cols` columns (cols >= n: one row). Cells shrink so the grid fits `w`; returns
   * { cell, gap, pos: [{x, y}] (centres, box-relative), width, height }.
   */
  function grid(n, o) {
    const cols = Math.min(n, o.cols || n), rows = Math.ceil(n / cols);
    const gapK = o.gap ?? 0.14;
    // w = cols * cell + (cols - 1) * gap, gap = gapK * cell
    const fit = o.w ? o.w / (cols + (cols - 1) * gapK) : Infinity;
    const cell = Math.min(o.cell || fit, fit), gap = cell * gapK, rowGap = o.rowGap ?? gap;
    const width = cols * cell + (cols - 1) * gap, height = rows * cell + (rows - 1) * rowGap;
    const pos = Array.from({ length: n }, (_, i) => ({
      x: (i % cols) * (cell + gap) + cell / 2,
      y: Math.floor(i / cols) * (cell + rowGap) + cell / 2,
    }));
    return { cell, gap, pos, width, height };
  }

  /**
   * A tree { id, kids: [...] } on a tidy layout: leaves take consecutive slots left to right, a parent sits over the
   * middle of its first and last child. Returns { nodes: [{ id, parent, depth, ux, uy }], leaves, depth } with ux in
   * [0, 1] and uy in [0, 1] (depth / max depth); one node: centred.
   */
  function tree(rootNode) {
    const nodes = []; let leaf = 0, maxDepth = 0;
    (function walk(n, depth, parent) {
      const rec = { id: n.id, parent, depth, ux: 0, uy: 0 }; nodes.push(rec);
      maxDepth = Math.max(maxDepth, depth);
      const kids = n.kids || [];
      if (!kids.length) { rec.slot = leaf++; return; }
      const idx = kids.map((k) => { const before = nodes.length; walk(k, depth + 1, n.id); return before; });
      rec.slot = (nodes[idx[0]].slot + nodes[idx[idx.length - 1]].slot) / 2;
    })(rootNode, 0, null);
    const span = Math.max(1, leaf - 1);
    for (const r of nodes) { r.ux = leaf === 1 ? 0.5 : r.slot / span; r.uy = maxDepth ? r.depth / maxDepth : 0.5; delete r.slot; }
    return { nodes, leaves: leaf, depth: maxDepth };
  }

  /** n points on a circle starting at the top and going clockwise (centres, box-relative). */
  function circle(n, cx, cy, r) {
    return Array.from({ length: n }, (_, i) => ({ x: cx + r * Math.sin((2 * Math.PI * i) / n), y: cy - r * Math.cos((2 * Math.PI * i) / n) }));
  }

  /** Where a ray from the centre of a box (w x h) toward (dx, dy) leaves it; circles use w = h. */
  function exit(shape, w, h, dx, dy) {
    const d = Math.hypot(dx, dy) || 1, ux = dx / d, uy = dy / d;
    if (shape === 'circle') return { x: ux * w / 2, y: uy * w / 2 };
    const k = Math.min(Math.abs(ux) > 1e-9 ? w / 2 / Math.abs(ux) : Infinity, Math.abs(uy) > 1e-9 ? h / 2 / Math.abs(uy) : Infinity);
    return { x: ux * k, y: uy * k };
  }

  return { grid, tree, circle, exit };
});
