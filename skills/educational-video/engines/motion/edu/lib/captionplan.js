// Pure planning for burned-in captions: normalise word timings, split caption cues into words, group words into pages
// of at most N lines, find the word being spoken. No DOM; loads as a classic <script> (window.CaptionPlan) or through
// require().
//
// Word timings are a flat list in SECONDS on the film's clock:
//   [{ "w": "Halve", "t": 0.42, "e": 0.71 }, { "w": "the", "t": 0.71, "e": 0.83 }, ...]
// w = the word as it should be shown (punctuation attached: "list."), t = when it starts, e = when it ends (optional:
// defaults to the next word's start, at most 0.6 s). Also accepted: word|text for w, start|s|from for t, end|to for e.
(function (root, factory) {
  const P = factory();
  if (typeof module === 'object' && module.exports) module.exports = P;
  else root.CaptionPlan = P;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const pick = (o, ...keys) => { for (const k of keys) if (o[k] != null) return o[k]; return undefined; };

  /** Any accepted shape -> [{ w, t, e }] sorted by start, with every end filled in and never past the next start. */
  function normalize(list) {
    const raw = (list || []).map((x, i) => {
      const w = pick(x, 'w', 'word', 'text'), t = pick(x, 't', 'start', 's', 'from'), e = pick(x, 'e', 'end', 'to');
      if (typeof w !== 'string' || !w.trim()) throw new Error(`captions: word ${i} has no text`);
      if (!Number.isFinite(t)) throw new Error(`captions: word ${i} ("${w}") has no start time`);
      return { w: w.trim(), t, e };
    }).sort((a, b) => a.t - b.t);
    return raw.map((x, i) => {
      const next = raw[i + 1] ? raw[i + 1].t : Infinity;
      let e = Number.isFinite(x.e) ? x.e : Math.min(next, x.t + 0.6);
      e = Math.max(x.t + 0.05, Math.min(e, next > x.t ? next : e));
      return { w: x.w, t: x.t, e };
    });
  }

  /** Caption cues [{ text, start, end }] -> words, each cue's time shared out by character count. */
  function fromCues(cues) {
    const out = [];
    for (const c of cues) {
      const ws = String(c.text).split(/\s+/).filter(Boolean), total = ws.reduce((a, w) => a + w.length + 1, 0);
      let t = c.start;
      for (const w of ws) { const d = ((w.length + 1) / total) * (c.end - c.start); out.push({ w, t, e: t + d }); t += d; }
    }
    return out;
  }

  const ENDS = /[.!?]["')\]]?$/, SOFT = /[,;:—]["')\]]?$/;

  /**
   * Group words into pages. opts: { maxChars: per line (28), maxLines: 2, maxWords: 8, gap: silence that closes a page (0.7 s), hold: 0.25 s a finished page stays }
   * returns [{ from, to, words: [index...], lines: [[index...]] }]; `to` never passes the next page's `from`.
   */
  function pages(words, o = {}) {
    const maxChars = o.maxChars ?? 28, maxLines = o.maxLines ?? 2, maxWords = o.maxWords ?? 8, gap = o.gap ?? 0.7, hold = o.hold ?? 0.25;
    const out = []; let cur = [];
    const lineCount = (idx) => { let n = 1, len = 0; for (const i of idx) { const l = words[i].w.length; if (len && len + 1 + l > maxChars) { n++; len = l; } else len += (len ? 1 : 0) + l; } return n; };
    const flush = () => { if (cur.length) out.push(cur); cur = []; };
    words.forEach((w, i) => {
      if (cur.length) {
        const prev = words[cur[cur.length - 1]];
        if (w.t - prev.e > gap || lineCount([...cur, i]) > maxLines || cur.length >= maxWords) flush();
      }
      cur.push(i);
      // close a sentence at its end, and a clause at a comma once the page has some weight
      if (ENDS.test(w.w) || (SOFT.test(w.w) && cur.length >= 4)) flush();
    });
    flush();
    return out.map((idx, k) => {
      const lines = []; let line = [], len = 0;
      for (const i of idx) { const l = words[i].w.length; if (line.length && len + 1 + l > maxChars) { lines.push(line); line = []; len = 0; } len += (line.length ? 1 : 0) + l; line.push(i); }
      if (line.length) lines.push(line);
      const from = words[idx[0]].t, end = words[idx[idx.length - 1]].e + hold;
      const nextFrom = out[k + 1] ? words[out[k + 1][0]].t : Infinity;
      return { from, to: Math.min(end, nextFrom), words: idx, lines };
    });
  }

  /** Index of the word being spoken at t (the last one that has started and not ended), or -1 between words. */
  function activeIndex(words, t) {
    let r = -1;
    for (let i = 0; i < words.length; i++) { if (words[i].t <= t) r = t < words[i].e ? i : -1; else break; }
    return r;
  }

  return { normalize, fromCues, pages, activeIndex };
});
