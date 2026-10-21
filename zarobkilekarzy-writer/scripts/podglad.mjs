#!/usr/bin/env node
// Podgląd artykułu w wyglądzie zarobkilekarzy.pl.
//
// Pobiera ze strony szablon podglądu (/podglad-autora/ — układ artykułu; style i fonty osadza w pliku),
// podmienia w nim tytuł, lead, „W skrócie”, spis treści, treść i przypisy na tekst z pliku Markdown
// i zapisuje jeden plik HTML obok szkicu. Gdy szablonu nie ma, bierze wzór z prawdziwego artykułu.
// Wymaga Node 18+; bez zależności. Łączy się tylko z zarobkilekarzy.pl.
//
// Użycie: node podglad.mjs artykul-temat.md [--wzor https://zarobkilekarzy.pl/<adres artykułu>/]
// Redakcja może sprawdzić szablon na lokalnym buildzie: PODGLAD_STRONA=http://localhost:4361

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const SITE = (process.env.PODGLAD_STRONA || 'https://zarobkilekarzy.pl').replace(/\/$/, '');
/** stały szablon, a gdy go nie ma (np. starsza wersja strony) — prawdziwy artykuł */
const DEFAULT_TEMPLATES = [`${SITE}/podglad-autora/`, `${SITE}/mechanizmy/kontrakt-vs-etat/`];
const SECTIONS = {
  Mechanizm: { label: 'Mechanizmy', href: '/mechanizmy/' },
  Dane: { label: 'Dane', href: '/dane/' },
  Analiza: { label: 'Analizy', href: '/analizy/' },
  Przewodnik: { label: 'Dla pacjenta', href: '/prawa-pacjenta/' },
};
const ILLUSTRATIONS = 'Propozycje ilustracji';
const EDITORS = 'Dla redakcji';

// ---------- argumenty ----------

let input;
let templateUrl;
for (const args = process.argv.slice(2); args.length; ) {
  const arg = args.shift();
  if (arg === '--wzor') templateUrl = args.shift();
  else if (arg.startsWith('--')) fail(`Nieznana opcja ${arg}. Użycie: node podglad.mjs artykul-temat.md [--wzor <adres>]`);
  else input = arg;
}
if (!input) fail('Podaj plik szkicu: node podglad.mjs artykul-temat.md');
if (templateUrl !== undefined && !templateUrl?.startsWith(`${SITE}/`)) fail(`Wzór musi być stroną ${SITE}.`);

function fail(msg) {
  console.error(`Błąd: ${msg}`);
  process.exit(1);
}

// ---------- frontmatter (podzbiór YAML używany w szablonie) ----------

function parseFrontmatter(src) {
  const m = src.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!m) return { data: {}, body: src };
  const data = {};
  const lines = m[1].split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = stripComment(lines[i]);
    const kv = line.match(/^([A-Za-z]\w*):\s*(.*)$/);
    if (!kv) continue;
    const [, key, rest] = kv;
    if (rest === '>-' || rest === '>' || rest === '|' || rest === '|-') {
      const block = [];
      while (i + 1 < lines.length && /^\s+\S/.test(lines[i + 1])) block.push(lines[++i].trim());
      data[key] = rest.startsWith('>') ? block.join(' ') : block.join('\n');
    } else if (rest === '') {
      const items = [];
      while (i + 1 < lines.length && /^\s*-\s/.test(lines[i + 1])) {
        let item = lines[++i].replace(/^\s*-\s+/, '');
        while (i + 1 < lines.length && /^\s{4,}\S/.test(lines[i + 1]) && !/^\s*-\s/.test(lines[i + 1])) {
          item += ' ' + lines[++i].trim();
        }
        items.push(unquote(stripComment(item)));
      }
      data[key] = items;
    } else {
      data[key] = unquote(rest);
    }
  }
  return { data, body: src.slice(m[0].length) };
}

function stripComment(s) {
  // komentarz YAML: „ #” poza cudzysłowem
  let q = null;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) { if (c === q) q = null; continue; }
    if (c === '"' || c === "'") q = c;
    else if (c === '#' && (i === 0 || /\s/.test(s[i - 1]))) return s.slice(0, i).trimEnd();
  }
  return s.trimEnd();
}

function unquote(s) {
  const t = s.trim();
  if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) return t.slice(1, -1);
  return t;
}

// ---------- Markdown → HTML (podzbiór: nagłówki, akapity, listy, cytaty, tabele, przypisy) ----------

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/ł/g, 'l')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

function createRenderer(footnoteDefs) {
  const order = []; // kolejność pierwszego odwołania
  const refCount = {};

  function inline(text, { refs = true } = {}) {
    // gotowe fragmenty HTML trafiają do schowka, żeby regexy wyróżnień nie psuły adresów i identyfikatorów
    const stash = [];
    const keep = (html) => `\u0000${stash.push(html) - 1}\u0000`;
    let s = esc(text);
    s = s.replace(/`([^`]+)`/g, (_, code) => keep(`<code>${code}</code>`));
    if (!refs) s = s.replace(/\[\^[^\]]+\]/g, '');
    s = s.replace(/\[\^([^\]]+)\]/g, (_, id) => {
      if (!order.includes(id)) order.push(id);
      refCount[id] = (refCount[id] || 0) + 1;
      const n = order.indexOf(id) + 1;
      const suffix = refCount[id] > 1 ? `-${refCount[id]}` : '';
      const missing = footnoteDefs[id] ? '' : ' title="Brak definicji przypisu" style="outline:2px solid #c00"';
      return keep(`<sup><a id="user-content-fnref-${esc(id)}${suffix}" data-footnote-ref href="#user-content-fn-${esc(id)}"${missing}>${n}</a></sup>`);
    });
    s = s.replace(/\[(ŹRÓDŁO\?|DO SPRAWDZENIA[^\]]*|PYTANIE[^\]]*)\]/g, (_, gap) => keep(`<mark class="podglad-luka">[${gap}]</mark>`));
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => {
      const external = /^https?:/.test(href) && !href.startsWith(SITE);
      const url = href.startsWith('/') ? SITE + href : href;
      return keep(`<a href="${url}"${external ? ' target="_blank" rel="noopener"' : ''}>${emphasis(label)}</a>`);
    });
    s = s.replace(/&lt;(https?:\/\/\S+?)&gt;/g, (_, url) => keep(`<a href="${url}" target="_blank" rel="noopener">${url}</a>`));
    s = emphasis(s);
    while (/\u0000\d+\u0000/.test(s)) s = s.replace(/\u0000(\d+)\u0000/g, (_, k) => stash[k]);
    return s;
  }

  function emphasis(s) {
    return s
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^\p{L}\p{N}*])\*([^*\s][^*]*)\*/gu, '$1<em>$2</em>')
      .replace(/(^|[^\p{L}\p{N}])_([^_\s][^_]*)_(?=[^\p{L}\p{N}]|$)/gu, '$1<em>$2</em>');
  }

  function blocks(md) {
    const lines = md.split(/\r?\n/);
    const out = [];
    const headings = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      let m;
      if ((m = line.match(/^(#{2,4})\s+(.*)$/))) {
        const level = m[1].length;
        const text = m[2].trim();
        const id = slugify(text);
        if (level === 2) headings.push({ id, text });
        out.push(`<h${level} id="${id}">${inline(text)}</h${level}>`);
        i++;
      } else if (/^```/.test(line)) {
        const code = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
        i++;
        out.push(`<pre><code>${esc(code.join('\n'))}</code></pre>`);
      } else if (/^(-{3,}|\*{3,})\s*$/.test(line)) {
        out.push('<hr>');
        i++;
      } else if (/^>\s?/.test(line)) {
        const quote = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^>\s?/, ''));
        out.push(`<blockquote>${blocks(quote.join('\n')).html}</blockquote>`);
      } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
        const ordered = /^\s*\d+\./.test(line);
        const items = [];
        while (i < lines.length && (/^\s*([-*]|\d+\.)\s+/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && items.length))) {
          if (/^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ''));
          else items[items.length - 1] += ' ' + lines[i].trim();
          i++;
        }
        const tag = ordered ? 'ol' : 'ul';
        out.push(`<${tag}>${items.map((it) => `<li>${inline(it)}</li>`).join('')}</${tag}>`);
      } else if (/^\|.*\|\s*$/.test(line) && /^\|?\s*:?-{3,}/.test(lines[i + 1] || '')) {
        const row = (l) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
        const head = row(line);
        i += 2;
        const body = [];
        while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) body.push(row(lines[i++]));
        out.push(
          `<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead>` +
            `<tbody>${body.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`,
        );
      } else {
        const para = [lines[i++].trim()];
        while (
          i < lines.length &&
          lines[i].trim() &&
          !/^(#{2,4}\s|```|>|\s*([-*]|\d+\.)\s+|\|.*\|\s*$)/.test(lines[i])
        ) para.push(lines[i++].trim());
        out.push(`<p>${inline(para.join(' '))}</p>`);
      }
    }
    return { html: out.join('\n'), headings };
  }

  function footnotes() {
    const unused = Object.keys(footnoteDefs).filter((id) => !order.includes(id));
    if (!order.length && !unused.length) return { count: 0, items: '', missing: [], unused };
    const items = order.map((id, idx) => {
      const n = idx + 1;
      const def = footnoteDefs[id];
      const text = def ? inline(def) : '<mark class="podglad-luka">[brak definicji przypisu]</mark>';
      const backs = Array.from({ length: refCount[id] }, (_, k) => {
        const suffix = k ? `-${k + 1}` : '';
        return `<a data-footnote-backref class="data-footnote-backref" aria-label="Wróć do miejsca w tekście (przypis ${n})" href="#user-content-fnref-${esc(id)}${suffix}">↩${k ? `<sup>${k + 1}</sup>` : ''}</a>`;
      }).join('');
      return `<li id="user-content-fn-${esc(id)}"><p>${text} ${backs}</p></li>`;
    });
    for (const id of unused) {
      items.push(`<li id="user-content-fn-${esc(id)}"><p><mark class="podglad-luka">[brak odwołania w tekście: ${esc(id)}]</mark> ${inline(footnoteDefs[id], { refs: false })}</p></li>`);
    }
    return { count: order.length + unused.length, items: items.join(''), missing: order.filter((id) => !footnoteDefs[id]), unused };
  }

  return { blocks, inline, footnotes };
}

// ---------- podział szkicu ----------

function splitDraft(body) {
  const defs = {};
  const kept = [];
  const lines = body.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^\[\^([^\]]+)\]:\s*(.*)$/);
    if (m) {
      let text = m[2];
      while (i + 1 < lines.length && /^\s{2,}\S/.test(lines[i + 1])) text += ' ' + lines[++i].trim();
      defs[m[1]] = text;
    } else kept.push(lines[i]);
  }
  // sekcje specjalne: „Propozycje ilustracji” i „Dla redakcji” nie są częścią artykułu
  const special = {};
  const main = [];
  let current = null;
  for (const line of kept) {
    const h = line.match(/^##\s+(.*)$/);
    if (h) {
      const name = h[1].replace(/\s*←.*$/, '').trim();
      current = name === ILLUSTRATIONS || name === EDITORS ? name : null;
      if (current) { special[current] = []; continue; }
    }
    (current ? special[current] : main).push(line);
  }
  return { defs, main: main.join('\n'), illustrations: special[ILLUSTRATIONS]?.join('\n'), editors: special[EDITORS]?.join('\n') };
}

// ---------- pomocnicze do HTML wzoru ----------

function replaceOnce(html, re, fn, what) {
  let found = false;
  const out = html.replace(re, (...m) => { found = true; return fn(...m); });
  if (!found) fail(`Nie znaleziono w układzie strony: ${what}. Układ strony mógł się zmienić — zgłoś to na kontakt@zarobkilekarzy.pl albo podaj inny wzór przez --wzor.`);
  return out;
}

/** Zakres elementu od otwierającego tagu (indeks) do jego zamknięcia, z liczeniem zagnieżdżeń. */
function elementRange(html, start, tag) {
  const re = new RegExp(`<${tag}\\b|</${tag}>`, 'g');
  re.lastIndex = start;
  let depth = 0;
  let m;
  while ((m = re.exec(html))) {
    depth += m[0].startsWith('</') ? -1 : 1;
    if (depth === 0) return [start, m.index + m[0].length];
  }
  fail(`Nie udało się odczytać elementu <${tag}> we wzorze.`);
}

function attrsOf(tagHtml) {
  return (tagHtml.match(/\sdata-astro-cid-[\w-]+(?:="[^"]*")?/g) || []).join('');
}

async function fetchText(url, { optional = false } = {}) {
  let res;
  try {
    res = await fetch(url, { headers: { 'User-Agent': 'zarobkilekarzy-writer-podglad' } });
  } catch (err) {
    fail(`Brak połączenia z ${SITE} (${err.cause?.code || err.message}). Podgląd potrzebuje internetu — sprawdź połączenie i spróbuj ponownie.`);
  }
  if (res.status === 404 && optional) return null;
  if (!res.ok) fail(`Nie udało się pobrać ${url} (HTTP ${res.status}).`);
  return res.text();
}

async function inlineFonts(css) {
  const urls = [...new Set([...css.matchAll(/url\("?(\/_astro\/fonts\/[^")]+)"?\)/g)].map((m) => m[1]))];
  const data = {};
  await Promise.all(
    urls.map(async (u) => {
      try {
        const res = await fetch(SITE + u);
        if (res.ok) data[u] = `data:font/woff2;base64,${Buffer.from(await res.arrayBuffer()).toString('base64')}`;
      } catch {
        // bez tego fontu podgląd użyje kroju zastępczego
      }
    }),
  );
  return css
    .replace(/url\("?(\/_astro\/fonts\/[^")]+)"?\)/g, (m, u) => (data[u] ? `url("${data[u]}")` : `url("${SITE}${u}")`))
    .replace(/url\("?(\/[^")]+)"?\)/g, (m, u) => `url("${SITE}${u}")`);
}

// ---------- składanie ----------

const src = await readFile(input, 'utf8');
const { data, body } = parseFrontmatter(src);
const draft = splitDraft(body);
const r = createRenderer(draft.defs);
const warnings = [];

const categoryKey = Object.keys(SECTIONS).find((k) => k.toLowerCase() === String(data.category || '').trim().toLowerCase());
if (!categoryKey) warnings.push(`Nieznana kategoria „${data.category || ''}” — dozwolone: ${Object.keys(SECTIONS).join(', ')}. W podglądzie: Analiza.`);
const section = SECTIONS[categoryKey || 'Analiza'];
const title = (data.title || '').replace(/\.\s*$/, '');
const keyPoints = Array.isArray(data.keyPoints) ? data.keyPoints : [];

// kolejność renderowania = kolejność czytania, żeby numery przypisów szły od góry strony
const titleHtml = title ? r.inline(title) : '<mark class="podglad-luka">[brak title]</mark>';
const leadHtml = data.summary ? r.inline(data.summary) : '<mark class="podglad-luka">[brak summary]</mark>';
const pointsHtml = keyPoints.map((k) => r.inline(k));
const content = r.blocks(draft.main);
const illustrations = draft.illustrations?.trim() ? r.blocks(draft.illustrations).html : '';
const notes = r.footnotes();
const editors = draft.editors?.trim() ? createRenderer({}).blocks(draft.editors).html : '';

const words = draft.main.replace(/\[\^[^\]]+\]/g, '').split(/\s+/).filter(Boolean).length;
const minutes = Math.max(1, Math.round(words / 200));
const today = new Date();
const pad = (n) => String(n).padStart(2, '0');
const isoDate = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
const plDate = `${pad(today.getDate())}.${pad(today.getMonth() + 1)}.${today.getFullYear()}`;
const gaps = (src.match(/\[(ŹRÓDŁO\?|DO SPRAWDZENIA[^\]]*|PYTANIE[^\]]*)\]/g) || []).length;

let html = null;
for (const url of templateUrl ? [templateUrl] : DEFAULT_TEMPLATES) {
  html = await fetchText(url, { optional: !templateUrl });
  if (html) break;
}
if (!html) fail(`Nie znaleziono szablonu podglądu na ${SITE}.`);
const layoutError = (what) => fail(`Nie znaleziono w układzie strony: ${what}. Układ strony mógł się zmienić — zgłoś to na kontakt@zarobkilekarzy.pl albo podaj inny wzór przez --wzor.`);

// <head>: bez skryptów zewnętrznych, preloadów i metadanych wzoru; style z osadzonymi fontami
const headOpen = html.match(/<head\b[^>]*>/);
const headEnd = html.indexOf('</head>');
if (!headOpen || headEnd < 0) layoutError('<head>');
const headStart = headOpen.index;
const styles = [...html.slice(headStart, headEnd).matchAll(/<style[^>]*>[\s\S]*?<\/style>/g)].map((m) => m[0]);
const css = await inlineFonts(styles.join('\n'));
const head =
  `<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">` +
  `<meta name="robots" content="noindex"><title>Podgląd: ${esc(title || 'szkic')}</title>` +
  `<meta name="color-scheme" content="light dark">${css}` +
  `<style>
    .podglad-pasek{position:sticky;top:0;z-index:9999;background:#b45309;color:#fff;font:600 14px/1.4 system-ui,sans-serif;padding:8px 16px}
    .podglad-pasek details{font-weight:400;margin-top:4px}
    .podglad-pasek summary{cursor:pointer}
    .podglad-pasek .podglad-redakcja{background:#fff;color:#111;padding:8px 12px;margin-top:6px;max-height:40vh;overflow:auto}
    mark.podglad-luka{background:#fde68a;color:#111;padding:0 2px}
  </style>`;
html = html.slice(0, headStart) + `<head>${head}` + html.slice(headEnd);

// usuń wszystkie skrypty i odnośniki względne zamień na adresy strony
html = html.replace(/<script\b[\s\S]*?<\/script>/g, '');
html = html.replace(/(href|src)="\/(?!\/)/g, `$1="${SITE}/`);

// <main>: zostaje tylko sekcja artykułu (bez „Powiązanych” i ramki postulatu wzoru)
const mainStart = html.search(/<main\b/);
if (mainStart < 0) layoutError('<main>');
const [, mainEnd] = elementRange(html, mainStart, 'main');
const mainOpen = html.slice(mainStart, html.indexOf('>', mainStart) + 1);
const articleStart = html.slice(mainStart).search(/<section\b/) + mainStart;
if (articleStart < mainStart) layoutError('sekcja artykułu');
const [, articleEnd] = elementRange(html, articleStart, 'section');
let article = html.slice(articleStart, articleEnd);

// Dopasowania tolerują odstępy między tagami, dodatkowe klasy i atrybuty.
const S = '\\s*';
const cls = (name) => `class="[^"]*\\b${name}\\b[^"]*"`;
const rx = (src) => new RegExp(src);

// okruszki: drugi element = dział, ostatni = tytuł
article = replaceOnce(article, rx(`(<nav[^>]*${cls('crumbs')}[\\s\\S]*?<li[^>]*>${S}<a[^>]*>[^<]*</a>${S}</li>${S}<li[^>]*>${S}<a href=")[^"]*("[^>]*>)[^<]*(</a>)`),
  (_, a, b, c) => `${a}${SITE}${section.href}${b}${section.label}${c}`, 'okruszki');
article = replaceOnce(article, rx(`(<nav[^>]*${cls('crumbs')}[\\s\\S]*?<span[^>]*aria-current="page"[^>]*>)[^<]*(</span>)`),
  (_, a, b) => `${a}${esc(title || 'Szkic')}${b}`, 'okruszki');
// nadtytuł, tytuł, lead
article = replaceOnce(article, rx(`(<p[^>]*${cls('eyebrow')}[^>]*>${S}<span[^>]*${cls('eyebrow__sq')}[^>]*>${S}</span>)[^<]*`), (_, a) => a + section.label, 'nadtytuł');
article = replaceOnce(article, rx(`(<h1[^>]*>)[\\s\\S]*?(<span[^>]*${cls('dot')}|</h1>)`), (_, a, b) => a + titleHtml + b, 'tytuł');
article = replaceOnce(article, rx(`(<p[^>]*${cls('ahead__lead')}[^>]*>)[\\s\\S]*?(</p>)`), (_, a, b) => a + leadHtml + b, 'lead');
// metryczka
article = replaceOnce(article, rx(`(<dt[^>]*>${S}Aktualizacja${S}</dt>${S}<dd[^>]*>${S}<time[^>]*datetime=")[^"]*("[^>]*>)[^<]*`), (_, a, b) => `${a}${isoDate}${b}${plDate}`, 'data');
article = article.replace(rx(`(<dt[^>]*>${S}Czas czytania${S}</dt>${S}<dd[^>]*>)[^<]*`), (_, a) => `${a}${minutes} min`);
article = article.replace(rx(`(<dt[^>]*>${S}Przypisy${S}</dt>${S}<dd[^>]*>)${S}<a[^>]*>[^<]*</a>`), (_, a, b) =>
  notes.count ? `${a}<a href="#przypisy">${notes.count} ze źródłami</a>` : `${a}<mark class="podglad-luka">[brak przypisów]</mark>`);
// W skrócie
article = replaceOnce(article, rx(`(<aside[^>]*${cls('ahead__points')}[\\s\\S]*?<ol[^>]*>)([\\s\\S]*?)(</ol>)`), (_, open, items, close) => {
  const li = items.match(/<li[^>]*>/)?.[0] || '<li>';
  const num = items.match(/<span[^>]*class="[^"]*\bnum\b[^"]*"[^>]*>/)?.[0] || '<span class="num num--sm">';
  const numInner = items.match(/<span[^>]*class="[^"]*\bnum\b[^"]*"[^>]*>\s*\d+\s*<span([^>]*)>/)?.[1] || '';
  const p = items.match(/<p[^>]*>/)?.[0] || '<p>';
  const body = pointsHtml.length
    ? pointsHtml.map((k, idx) => `${li}${num}${pad(idx + 1)}<span${numInner}>.</span></span>${p}${k}</p></li>`).join('')
    : `${li}${p}<mark class="podglad-luka">[brak keyPoints]</mark></p></li>`;
  return open + body + close;
}, '„W skrócie”');
// spis treści (bez odwołań do przypisów — te są już w nagłówkach treści)
article = article.replace(/(<zl-toc[\s\S]*?<ol[^>]*>)([\s\S]*?)(<\/ol>)/, (_, open, items, close) => {
  const li = items.match(/<li[^>]*>/)?.[0] || '<li>';
  const a = attrsOf(items.match(/<a[^>]*>/)?.[0] || '');
  return open + content.headings.map((h) => `${li}<a href="#${h.id}"${a}>${r.inline(h.text, { refs: false })}</a></li>`).join('') + close;
});
// treść i przypisy
const proseStart = article.search(/<div[^>]*class="[^"]*\bprose\b/);
if (proseStart < 0) layoutError('treść artykułu (.prose)');
const [, proseEnd] = elementRange(article, proseStart, 'div');
const proseOpen = article.slice(proseStart, article.indexOf('>', proseStart) + 1);
const proseOld = article.slice(proseStart, proseEnd);
const asideOpen = proseOld.match(/<aside[^>]*class="[^"]*\baside--note\b[^"]*"[^>]*>/)?.[0];
const asideCid = attrsOf(asideOpen || '');
const footHead = proseOld.match(/<details[^>]*class="[^"]*\bfootnotes\b[^"]*"[\s\S]*?<\/summary>/)?.[0];
let prose = content.html;
if (illustrations) {
  prose += asideOpen
    ? `${asideOpen}<p class="aside__label"${asideCid}>Dla redakcji</p><p class="aside__title"${asideCid}>${ILLUSTRATIONS}</p><div class="aside__body"${asideCid}>${illustrations}</div></aside>`
    : `<blockquote><p><strong>${ILLUSTRATIONS}</strong></p>${illustrations}</blockquote>`;
}
if (notes.count) {
  const summary = footHead
    ? footHead.replace(/(Przypisy\s*<span>)\d+(<\/span>)/, `$1${notes.count}$2`)
    : `<details class="footnotes" id="przypisy"><summary>Przypisy ${notes.count}</summary>`;
  prose += `${summary}<ol>${notes.items}</ol></details>`;
}
article = article.slice(0, proseStart) + proseOpen + prose + '</div>' + article.slice(proseEnd);

if (!title || !data.summary || !keyPoints.length) warnings.push('Brakuje title, summary albo keyPoints — w podglądzie oznaczone na żółto.');
if (keyPoints.length > 4) warnings.push(`„W skrócie” ma ${keyPoints.length} punktów (najwyżej 4).`);
if (notes.missing.length) warnings.push(`Odwołania do przypisów bez definicji: ${notes.missing.join(', ')}.`);
if (notes.unused.length) warnings.push(`Przypisy bez odwołania w tekście: ${notes.unused.join(', ')}.`);
// źródła są w przypisach — w treści zostają tylko odnośniki do innych stron serwisu
const proseUrls = [...`${draft.main}\n${data.summary || ''}\n${keyPoints.join('\n')}`.matchAll(/https?:\/\/[^\s)<>"\]]+/g)]
  .map((m) => m[0])
  .filter((url) => !url.startsWith(`${SITE}/`) && url !== SITE);
if (proseUrls.length) {
  warnings.push(`Linki do źródeł w treści (${proseUrls.length}) — źródła idą do przypisów [^id]: ${proseUrls.slice(0, 3).join(', ')}${proseUrls.length > 3 ? ', …' : ''}.`);
}

const banner =
  `<div class="podglad-pasek" role="note">Podgląd lokalny szkicu — nieopublikowane · ${esc(path.basename(input))} · ` +
  `${words} słów · luk do uzupełnienia: ${gaps}` +
  warnings.map((w) => `<br>Uwaga: ${esc(w)}`).join('') +
  (editors ? `<details><summary>Dla redakcji</summary><div class="podglad-redakcja">${editors}</div></details>` : '') +
  `</div>`;

html = html.slice(0, mainStart) + mainOpen + article + '</main>' + html.slice(mainEnd);
html = html.replace(/<body([^>]*)>/, (_, attrs) => `<body${attrs}>${banner}`);

const outFile = input.replace(/\.md$/i, '') + '.podglad.html';
await writeFile(outFile, html, 'utf8');
console.log(`Zapisano podgląd: ${path.resolve(outFile)}`);
for (const w of warnings) console.log(`Uwaga: ${w}`);
