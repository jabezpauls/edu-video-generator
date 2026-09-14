// A small syntax highlighter for lesson code: enough to colour keywords, strings, numbers, comments and calls
// correctly in the languages lessons use, with no dependency. Pure; loads as a classic <script> (window.Tokens) or
// through require().
//
//   tokenize(code, 'python') -> lines: [[{ c: 'kw'|'str'|'num'|'com'|'fn'|'op'|null, s: 'text' }, ...], ...]
//   one entry per source line; a comment or string that spans lines is split per line. Concatenating the `s` of a
//   line gives the line back exactly.
(function (root, factory) {
  const T = factory();
  if (typeof module === 'object' && module.exports) module.exports = T;
  else root.Tokens = T;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const words = (s) => new Set(s.split(/\s+/).filter(Boolean));
  const LANGS = {
    python: { kw: words('def class return if elif else for while in not and or is import from as with try except finally raise pass break continue lambda yield global nonlocal assert del None True False async await'),
      line: ['#'], block: null, strings: ['"""', "'''", '"', "'"] },
    javascript: { kw: words('function return if else for while do of in new class extends const let var import from export default async await try catch finally throw switch case break continue typeof instanceof this null undefined true false yield static'),
      line: ['//'], block: ['/*', '*/'], strings: ['`', '"', "'"] },
    c: { kw: words('int long short char float double void unsigned signed const static struct enum union typedef return if else for while do switch case break continue sizeof goto auto register extern volatile bool true false NULL class public private protected new delete this nullptr using namespace template typename fn let mut pub impl match func go package import interface string var range defer'),
      line: ['//'], block: ['/*', '*/'], strings: ['"', "'"] },
    bash: { kw: words('if then else elif fi for while do done in case esac function return export local echo cd set unset'),
      line: ['#'], block: null, strings: ['"', "'"] },
    json: { kw: words('true false null'), line: [], block: null, strings: ['"'] },
    sql: { kw: words('select from where group by order having join left right inner outer on as and or not in is null insert into values update set delete create table index limit distinct union all case when then else end'),
      line: ['--'], block: ['/*', '*/'], strings: ["'", '"'] },
    text: { kw: new Set(), line: [], block: null, strings: [] },
  };
  const ALIAS = { py: 'python', js: 'javascript', ts: 'javascript', typescript: 'javascript', jsx: 'javascript', tsx: 'javascript',
    java: 'c', cpp: 'c', 'c++': 'c', cs: 'c', go: 'c', rust: 'c', rs: 'c', sh: 'bash', shell: 'bash', zsh: 'bash',
    plain: 'text', txt: 'text', pseudo: 'python', pseudocode: 'python' };

  const lang = (name) => LANGS[ALIAS[name] || name] || LANGS.text;
  const IDENT = /[A-Za-z_$][\w$]*/y, NUM = /(?:0[xX][\da-fA-F_]+|\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?|\.\d+)/y, SPACE = /\s+/y;

  function tokenize(code, name = 'text') {
    const L = lang(name);
    const lines = [[]];
    const push = (c, s) => {
      const parts = s.split('\n');
      parts.forEach((p, i) => { if (i) lines.push([]); if (p) lines[lines.length - 1].push({ c, s: p }); });
    };
    // a span that may run past the end of the line: block comments and triple-quoted or backtick strings
    const spanTo = (i, close) => { const j = code.indexOf(close, i); return j < 0 ? code.length : j + close.length; };
    let i = 0, prevWord = null;
    while (i < code.length) {
      const ch = code[i];
      if (ch === '\n') { lines.push([]); i++; continue; }
      SPACE.lastIndex = i;
      const sp = SPACE.exec(code);
      if (sp && sp.index === i) {
        const w = sp[0], nl = w.indexOf('\n');
        const cut = nl < 0 ? w : w.slice(0, nl);
        if (cut) lines[lines.length - 1].push({ c: null, s: cut });
        i += cut.length; continue;
      }
      const lc = L.line.find((m) => code.startsWith(m, i));
      if (lc) { const j = code.indexOf('\n', i); const e = j < 0 ? code.length : j; push('com', code.slice(i, e)); i = e; continue; }
      if (L.block && code.startsWith(L.block[0], i)) { const e = spanTo(i + L.block[0].length, L.block[1]); push('com', code.slice(i, e)); i = e; continue; }
      const q = L.strings.find((m) => code.startsWith(m, i));
      if (q) {
        let j = i + q.length;
        const multi = q.length === 3 || q === '`';
        while (j < code.length) {
          if (code[j] === '\\') { j += 2; continue; }
          if (code.startsWith(q, j)) { j += q.length; break; }
          if (code[j] === '\n' && !multi) break;
          j++;
        }
        j = Math.min(j, code.length);
        push('str', code.slice(i, j)); i = j; continue;
      }
      IDENT.lastIndex = i;
      const id = IDENT.exec(code);
      if (id && id.index === i) {
        const w = id[0]; let c = null;
        if (L.kw.has(w) || L.kw.has(w.toLowerCase()) && name === 'sql') c = 'kw';
        else if (code[i + w.length] === '(' || /^(?:def|function|fn|func|class)$/.test(prevWord || '')) c = 'fn';
        push(c, w); prevWord = w; i += w.length; continue;
      }
      NUM.lastIndex = i;
      const nm = /\d|\.\d/.test(code.slice(i, i + 2)) ? NUM.exec(code) : null;
      if (nm && nm.index === i) { push('num', nm[0]); i += nm[0].length; prevWord = null; continue; }
      push('op', ch); i++; prevWord = null;
    }
    return lines;
  }

  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  /** The first n characters of a tokenized line, as html spans (n omitted: the whole line). */
  function html(line, n = Infinity) {
    let out = '', left = n;
    for (const tk of line) {
      if (left <= 0) break;
      const s = tk.s.length <= left ? tk.s : tk.s.slice(0, left);
      left -= s.length;
      out += tk.c ? `<span class="t-${tk.c}">${esc(s)}</span>` : esc(s);
    }
    return out;
  }
  const length = (line) => line.reduce((a, tk) => a + tk.s.length, 0);

  return { tokenize, html, length, LANGS };
});
