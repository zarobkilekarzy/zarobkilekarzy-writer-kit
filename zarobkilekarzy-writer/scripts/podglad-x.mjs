#!/usr/bin/env node
// Podgląd wpisu albo wątku na X z konta @ZarobkiLekarzy.
//
// Czyta plik x-<temat>.md (formaty.md, część B) i zapisuje obok plik HTML z wpisami tak, jak na osi czasu X:
// avatar i nazwa konta, tekst z linkami, karta linku do zarobkilekarzy.pl, licznik znaków liczony jak na X,
// tryb jasny i ciemny obok siebie. Wymaga Node 18+; bez zależności. Łączy się tylko z zarobkilekarzy.pl
// (karta linku); bez internetu podgląd powstaje bez karty. To samo robi podglad-x.py (identyczny wynik).
//
// Użycie: node podglad-x.mjs x-temat.md

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = (process.env.PODGLAD_STRONA || 'https://zarobkilekarzy.pl').replace(/\/$/, '');
const ACCOUNT = { name: 'zarobkilekarzy.pl', handle: '@ZarobkiLekarzy' };
const LIMIT = 280;
const URL_LENGTH = 23;
const URL_RE = /https?:\/\/[^\s<>"]+[^\s<>".,;:!?)\]'”]/g;
/** emoji jako jawne zakresy (te same w podglad-x.py): flaga z dwóch liter regionalnych albo znak z modyfikatorami */
const EMOJI_BASE = '[\\u{1F000}-\\u{1FAFF}\\u2600-\\u27BF\\u2B00-\\u2BFF\\u2300-\\u23FF]';
const EMOJI_RE = new RegExp(`[\\u{1F1E6}-\\u{1F1FF}]{2}|${EMOJI_BASE}(?:\\uFE0F|[\\u{1F3FB}-\\u{1F3FF}]|\\u200D${EMOJI_BASE})*`, 'gu');

function fail(msg) {
  console.error(`Błąd: ${msg}`);
  process.exit(1);
}

const input = process.argv[2];
if (!input || input.startsWith('--')) fail('Podaj plik wpisu: node podglad-x.mjs x-temat.md');

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// ---------- plik wpisu ----------

/** Sekcje „## …”: wpisy („Wpis 1/N”), propozycja grafiki i notatka dla redakcji. */
function parsePost(src) {
  const sections = [];
  let current = null;
  for (const line of src.replace(/^\uFEFF/, '').split(/\r?\n/)) {
    const h = line.match(/^##\s+(.*)$/);
    if (h) {
      current = { title: h[1].trim(), lines: [] };
      sections.push(current);
    } else if (current) current.lines.push(line);
  }
  const text = (s) => s.lines.join('\n').trim();
  return {
    posts: sections.filter((s) => /^Wpis\b/i.test(s.title)).map(text),
    graphic: text(sections.find((s) => /^Propozycja grafiki/i.test(s.title)) || { lines: [] }),
    editors: text(sections.find((s) => /^Dla redakcji/i.test(s.title)) || { lines: [] }),
  };
}

// ---------- licznik znaków jak na X ----------

/**
 * Długość wpisu liczona jak na X (twitter-text, wersja 3): link = 23 znaki, emoji = 2, znaki z zakresów
 * łacińskich (także polskie litery), myślniki i cudzysłowy typograficzne = 1, pozostałe = 2.
 */
function weightedLength(text) {
  const plain = text.normalize('NFC').replace(URL_RE, '');
  const urls = (text.match(URL_RE) || []).length;
  let n = urls * URL_LENGTH;
  const rest = plain.replace(EMOJI_RE, () => { n += 2; return ''; });
  for (const ch of rest) {
    const c = ch.codePointAt(0);
    const light = c <= 0x10ff || (c >= 0x2000 && c <= 0x200d) || (c >= 0x2010 && c <= 0x201f) || (c >= 0x2032 && c <= 0x2037);
    n += light ? 1 : 2;
  }
  return n;
}

/** Adres w treści wpisu tak, jak pokazuje go X: bez protokołu i „www.”, ucięty po 23 znakach. */
function displayUrl(url) {
  const bare = [...url.replace(/^https?:\/\/(www\.)?/, '')];
  return bare.length > 25 ? `${bare.slice(0, 23).join('')}…` : bare.join('');
}

function renderText(text) {
  const stash = [];
  const keep = (html) => `\u0000${stash.push(html) - 1}\u0000`;
  let s = text.replace(URL_RE, (url) => keep(`<a class="link" href="${esc(url)}">${esc(displayUrl(url))}</a>`));
  s = esc(s)
    .replace(/(^|[^\p{L}\p{N}_@])([@#][\p{L}\p{N}_]+)/gu, '$1<span class="link">$2</span>')
    .replace(/\n/g, '<br>');
  return s.replace(/\u0000(\d+)\u0000/g, (_, k) => stash[k]);
}

// ---------- karta linku do zarobkilekarzy.pl ----------

async function fetchCard(url) {
  if (!url.startsWith(`${SITE}/`) && url !== SITE) return null;
  try {
    const res = await fetch(url, { headers: { 'User-Agent': 'zarobkilekarzy-writer-podglad' } });
    if (!res.ok) return { url, error: `HTTP ${res.status}` };
    const html = await res.text();
    const meta = (prop) => html.match(new RegExp(`<meta[^>]+property="og:${prop}"[^>]+content="([^"]*)"`))?.[1];
    const image = meta('image');
    let data = null;
    if (image) {
      const img = await fetch(image.replace(/&amp;/g, '&'));
      if (img.ok) data = `data:${img.headers.get('content-type') || 'image/png'};base64,${Buffer.from(await img.arrayBuffer()).toString('base64')}`;
    }
    return { url, title: meta('title'), image: data };
  } catch (err) {
    return { url, error: err.cause?.code || err.message };
  }
}

// ---------- ostrzeżenia ----------

function checkPost(text, i, total) {
  const w = [];
  const n = weightedLength(text);
  const label = total > 1 ? `Wpis ${i + 1}/${total}` : 'Wpis';
  if (n > LIMIT) w.push(`${label}: ${n}/${LIMIT} znaków — za długi o ${n - LIMIT}.`);
  if (!text.trim()) w.push(`${label}: pusty.`);
  const plain = text.replace(URL_RE, '');
  if (plain.includes('!')) w.push(`${label}: wykrzyknik — głos serwisu jest bez wykrzykników.`);
  if (/(^|[^\p{L}\p{N}_])@[\p{L}\p{N}_]/u.test(plain)) w.push(`${label}: oznaczenie konta (@…) — wpisy nie oznaczają osób.`);
  if (/[0-9]/.test(plain) && plain === text) w.push(`${label}: liczba bez linku do źródła.`);
  return w;
}

// ---------- HTML ----------

const ICONS = {
  reply: 'M2 11a7 7 0 0 1 7-7h6a7 7 0 0 1 0 14h-3l-5 4v-4.5A7 7 0 0 1 2 11z',
  repost: 'M5 7h11l-3-3M19 17H8l3 3M5 7v6M19 17v-6',
  like: 'M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z',
  views: 'M5 20V12M10 20V6M15 20v-9M20 20V9',
  share: 'M12 4v11M7 9l5-5 5 5M5 14v5h14v-5',
};
const actions = Object.values(ICONS)
  .map((d) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`)
  .join('');

function renderPost(text, i, total, avatar, card, graphic) {
  const n = weightedLength(text);
  const media = graphic && i === 0
    ? `<div class="graphic"><span>Propozycja grafiki</span>${renderText(graphic)}</div>`
    : card?.image
      ? `<div class="card"><img src="${card.image}" alt=""><span class="card__domain">${esc(new URL(card.url).host)}</span></div><p class="card__from">Z: ${esc(new URL(card.url).host)}</p>`
      : '';
  return `<article class="post${i < total - 1 ? ' post--thread' : ''}">
  <div class="post__side"><img class="avatar" src="${avatar}" alt=""></div>
  <div class="post__main">
    <p class="post__head"><strong>${ACCOUNT.name}</strong> <span>${ACCOUNT.handle} · teraz</span></p>
    <div class="post__text">${renderText(text)}</div>
    ${media}
    <div class="post__actions">${actions}</div>
    <p class="post__count${n > LIMIT ? ' post__count--over' : ''}">${total > 1 ? `${i + 1}/${total} · ` : ''}${n}/${LIMIT} znaków</p>
  </div>
</article>`;
}

// ---------- składanie ----------

let src;
try {
  src = await readFile(input, 'utf8');
} catch (err) {
  fail(`Nie mogę odczytać pliku ${input} (${err.code}).`);
}
const { posts, graphic, editors } = parsePost(src);
if (!posts.length) fail('Nie znalazłem żadnego wpisu. Każdy wpis zaczyna się od nagłówka „## Wpis 1/N” (formaty.md, część B).');

const here = path.dirname(fileURLToPath(import.meta.url));
const avatar = `data:image/png;base64,${(await readFile(path.join(here, 'avatar-x.png'))).toString('base64')}`;

// X pokazuje kartę ostatniego linku we wpisie (gdy wpis nie ma grafiki)
const cards = await Promise.all(posts.map((p) => {
  const urls = p.match(URL_RE) || [];
  return urls.length ? fetchCard(urls[urls.length - 1]) : null;
}));

const warnings = posts.flatMap((p, i) => checkPost(p, i, posts.length));
for (const c of cards) if (c?.error) warnings.push(`Nie udało się pobrać karty linku ${c.url} (${c.error}) — podgląd bez obrazka.`);

/** 2–4, 22–24… wpisy; 5–21, 25… wpisów */
const postsWord = (n) => (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'wpisy' : 'wpisów');

const column = (theme) =>
  `<section class="col ${theme}"><p class="col__label">${theme === 'light' ? 'Tryb jasny' : 'Tryb ciemny'}</p>` +
  posts.map((p, i) => renderPost(p, i, posts.length, avatar, cards[i], graphic)).join('') +
  '</section>';

const html = `<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Podgląd wpisu na X: ${esc(path.basename(input))}</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #e6ecf0; font: 15px/20px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .bar { position: sticky; top: 0; z-index: 2; background: #b45309; color: #fff; font: 600 14px/1.4 system-ui, sans-serif; padding: 8px 16px; }
  .bar details { font-weight: 400; margin-top: 4px; }
  .bar summary { cursor: pointer; }
  .bar .notes { background: #fff; color: #111; padding: 8px 12px; margin-top: 6px; white-space: pre-wrap; max-height: 40vh; overflow: auto; }
  .cols { display: flex; flex-wrap: wrap; gap: 24px; justify-content: center; padding: 24px 16px; }
  .col { width: 100%; max-width: 600px; border: 1px solid var(--line); background: var(--bg); color: var(--text); }
  .col__label { margin: 0; padding: 8px 16px; font-size: 13px; color: var(--muted); border-bottom: 1px solid var(--line); }
  .light { --bg: #fff; --text: #0f1419; --muted: #536471; --line: #eff3f4; --link: #1d9bf0; }
  .dark { --bg: #000; --text: #e7e9ea; --muted: #71767b; --line: #2f3336; --link: #1d9bf0; }
  .post { display: flex; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--line); }
  .post--thread { border-bottom: 0; }
  .post__side { position: relative; flex: 0 0 40px; }
  .post--thread .post__side::after { content: ""; position: absolute; left: 19px; top: 44px; bottom: -16px; width: 2px; background: var(--line); }
  .avatar { width: 40px; height: 40px; border-radius: 50%; display: block; }
  .post__main { flex: 1; min-width: 0; }
  .post__head { margin: 0 0 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .post__head span { color: var(--muted); }
  .post__text { overflow-wrap: anywhere; }
  .link { color: var(--link); text-decoration: none; }
  .card { position: relative; margin-top: 12px; border: 1px solid var(--line); border-radius: 16px; overflow: hidden; }
  .card img { display: block; width: 100%; aspect-ratio: 1200 / 630; object-fit: cover; }
  .card__domain { position: absolute; left: 12px; bottom: 12px; padding: 0 4px; border-radius: 4px; background: rgba(0,0,0,.77); color: #fff; font-size: 13px; }
  .card__from { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
  .graphic { margin-top: 12px; padding: 16px; border: 2px dashed var(--muted); border-radius: 16px; color: var(--muted); }
  .graphic span { display: block; font-weight: 700; margin-bottom: 4px; }
  .post__actions { display: flex; justify-content: space-between; max-width: 425px; margin-top: 12px; }
  .post__actions svg { width: 18px; height: 18px; fill: none; stroke: var(--muted); stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  .post__count { margin: 8px 0 0; font-size: 13px; color: var(--muted); }
  .post__count--over { color: #f4212e; font-weight: 700; }
</style>
</head>
<body>
<div class="bar" role="note">Podgląd lokalny wpisu na X — nieopublikowane · ${esc(path.basename(input))} · ${posts.length === 1 ? '1 wpis' : `wątek: ${posts.length} ${postsWord(posts.length)}`}${warnings.map((w) => `<br>Uwaga: ${esc(w)}`).join('')}${editors ? `<details><summary>Dla redakcji</summary><div class="notes">${esc(editors)}</div></details>` : ''}</div>
<main class="cols">${column('light')}${column('dark')}</main>
</body>
</html>
`;

const outFile = input.replace(/\.md$/i, '') + '.podglad.html';
await writeFile(outFile, html, 'utf8');
console.log(`Zapisano podgląd: ${path.resolve(outFile)}`);
for (const w of warnings) console.log(`Uwaga: ${w}`);
