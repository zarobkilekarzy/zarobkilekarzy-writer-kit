#!/usr/bin/env python3
# Podgląd artykułu w wyglądzie zarobkilekarzy.pl — wersja w Pythonie (to samo co podglad.mjs).
#
# Pobiera ze strony szablon podglądu (/podglad-autora/ — układ artykułu; style i fonty osadza w pliku),
# podmienia w nim tytuł, lead, „W skrócie”, spis treści, treść i przypisy na tekst z pliku Markdown
# i zapisuje jeden plik HTML obok szkicu. Gdy szablonu nie ma, bierze wzór z prawdziwego artykułu.
# Wymaga Pythona 3.8+; tylko biblioteka standardowa. Łączy się tylko z zarobkilekarzy.pl.
#
# Użycie: python3 podglad.py artykul-temat.md [--wzor https://zarobkilekarzy.pl/<adres artykułu>/]
# Redakcja może sprawdzić szablon na lokalnym buildzie: PODGLAD_STRONA=http://localhost:4361

import base64
import datetime
import os
import re
import ssl
import sys
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, 'reconfigure'):
    # konsola Windows bez UTF-8 wywraca się na polskich znakach
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SITE = (os.environ.get('PODGLAD_STRONA') or 'https://zarobkilekarzy.pl').rstrip('/')
# stały szablon, a gdy go nie ma (np. starsza wersja strony) — prawdziwy artykuł
DEFAULT_TEMPLATES = [f'{SITE}/podglad-autora/', f'{SITE}/mechanizmy/kontrakt-vs-etat/']
SECTIONS = {
    'Mechanizm': {'label': 'Mechanizmy', 'href': '/mechanizmy/'},
    'Dane': {'label': 'Dane', 'href': '/dane/'},
    'Analiza': {'label': 'Analizy', 'href': '/analizy/'},
    'Przewodnik': {'label': 'Dla pacjenta', 'href': '/prawa-pacjenta/'},
}
ILLUSTRATIONS = 'Propozycje ilustracji'
EDITORS = 'Dla redakcji'
GAP_RE = r'\[(ŹRÓDŁO\?|DO SPRAWDZENIA[^\]]*|PYTANIE[^\]]*)\]'


def fail(msg):
    print(f'Błąd: {msg}', file=sys.stderr)
    sys.exit(1)


# ---------- argumenty ----------

def parse_args(argv):
    input_path, template_url = None, None
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == '--wzor':
            template_url = args.pop(0) if args else ''
        elif arg.startswith('--'):
            fail(f'Nieznana opcja {arg}. Użycie: python3 podglad.py artykul-temat.md [--wzor <adres>]')
        else:
            input_path = arg
    if not input_path:
        fail('Podaj plik szkicu: python3 podglad.py artykul-temat.md')
    if template_url is not None and not template_url.startswith(f'{SITE}/'):
        fail(f'Wzór musi być stroną {SITE}.')
    return input_path, template_url


# ---------- frontmatter (podzbiór YAML używany w szablonie) ----------

def strip_comment(s):
    # komentarz YAML: „ #” poza cudzysłowem
    q = None
    for i, c in enumerate(s):
        if q:
            if c == q:
                q = None
            continue
        if c in '"\'':
            q = c
        elif c == '#' and (i == 0 or s[i - 1].isspace()):
            return s[:i].rstrip()
    return s.rstrip()


def unquote(s):
    t = s.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in '"\'':
        return t[1:-1]
    return t


def parse_frontmatter(src):
    m = re.match(r'---\r?\n([\s\S]*?)\r?\n---\r?\n?', src)
    if not m:
        return {}, src
    data = {}
    lines = re.split(r'\r?\n', m.group(1))
    i = 0
    while i < len(lines):
        line = strip_comment(lines[i])
        kv = re.match(r'([A-Za-z]\w*):\s*(.*)$', line)
        if kv:
            key, rest = kv.group(1), kv.group(2)
            if rest in ('>-', '>', '|', '|-'):
                block = []
                while i + 1 < len(lines) and re.match(r'\s+\S', lines[i + 1]):
                    i += 1
                    block.append(lines[i].strip())
                data[key] = ' '.join(block) if rest.startswith('>') else '\n'.join(block)
            elif rest == '':
                items = []
                while i + 1 < len(lines) and re.match(r'\s*-\s', lines[i + 1]):
                    i += 1
                    item = re.sub(r'^\s*-\s+', '', lines[i])
                    while i + 1 < len(lines) and re.match(r'\s{4,}\S', lines[i + 1]) and not re.match(r'\s*-\s', lines[i + 1]):
                        i += 1
                        item += ' ' + lines[i].strip()
                    items.append(unquote(strip_comment(item)))
                data[key] = items
            else:
                data[key] = unquote(rest)
        i += 1
    return data, src[m.end():]


# ---------- Markdown → HTML (podzbiór: nagłówki, akapity, listy, cytaty, tabele, przypisy) ----------

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def slugify(text):
    s = unicodedata.normalize('NFD', text.lower().replace('ł', 'l'))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'[^\w\s-]|_', '', s).strip()
    return re.sub(r'-+', '-', re.sub(r'\s+', '-', s))


LIST_RE = r'\s*([-*]|\d+\.)\s+'


class Renderer:
    def __init__(self, footnote_defs):
        self.defs = footnote_defs
        self.order = []  # kolejność pierwszego odwołania
        self.ref_count = {}

    @staticmethod
    def emphasis(s):
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'(^|[^\w*]|_)\*([^*\s][^*]*)\*', r'\1<em>\2</em>', s)
        return re.sub(r'(^|\W|_)_([^_\s][^_]*)_(?=\W|_|$)', r'\1<em>\2</em>', s)

    def inline(self, text, refs=True):
        # gotowe fragmenty HTML trafiają do schowka, żeby regexy wyróżnień nie psuły adresów i identyfikatorów
        stash = []

        def keep(html):
            stash.append(html)
            return f'\x00{len(stash) - 1}\x00'

        def ref(m):
            fid = m.group(1)
            if fid not in self.order:
                self.order.append(fid)
            self.ref_count[fid] = self.ref_count.get(fid, 0) + 1
            n = self.order.index(fid) + 1
            suffix = f'-{self.ref_count[fid]}' if self.ref_count[fid] > 1 else ''
            missing = '' if fid in self.defs else ' title="Brak definicji przypisu" style="outline:2px solid #c00"'
            return keep(f'<sup><a id="user-content-fnref-{esc(fid)}{suffix}" data-footnote-ref '
                        f'href="#user-content-fn-{esc(fid)}"{missing}>{n}</a></sup>')

        def link(m):
            label, href = m.group(1), m.group(2)
            external = re.match(r'https?:', href) and not href.startswith(SITE)
            url = SITE + href if href.startswith('/') else href
            target = ' target="_blank" rel="noopener"' if external else ''
            return keep(f'<a href="{url}"{target}>{self.emphasis(label)}</a>')

        s = esc(text)
        s = re.sub(r'`([^`]+)`', lambda m: keep(f'<code>{m.group(1)}</code>'), s)
        if not refs:
            s = re.sub(r'\[\^[^\]]+\]', '', s)
        s = re.sub(r'\[\^([^\]]+)\]', ref, s)
        s = re.sub(GAP_RE, lambda m: keep(f'<mark class="podglad-luka">[{m.group(1)}]</mark>'), s)
        s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)
        s = re.sub(r'&lt;(https?://\S+?)&gt;', lambda m: keep(f'<a href="{m.group(1)}" target="_blank" rel="noopener">{m.group(1)}</a>'), s)
        s = self.emphasis(s)
        while re.search(r'\x00\d+\x00', s):
            s = re.sub(r'\x00(\d+)\x00', lambda m: stash[int(m.group(1))], s)
        return s

    def blocks(self, md):
        lines = re.split(r'\r?\n', md)
        out, headings = [], []
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            m = re.match(r'(#{2,4})\s+(.*)$', line)
            if m:
                level, text = len(m.group(1)), m.group(2).strip()
                hid = slugify(text)
                if level == 2:
                    headings.append({'id': hid, 'text': text})
                out.append(f'<h{level} id="{hid}">{self.inline(text)}</h{level}>')
                i += 1
            elif line.startswith('```'):
                code = []
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    code.append(lines[i])
                    i += 1
                i += 1
                out.append(f'<pre><code>{esc(chr(10).join(code))}</code></pre>')
            elif re.match(r'(-{3,}|\*{3,})\s*$', line):
                out.append('<hr>')
                i += 1
            elif re.match(r'>\s?', line):
                quote = []
                while i < len(lines) and re.match(r'>\s?', lines[i]):
                    quote.append(re.sub(r'^>\s?', '', lines[i]))
                    i += 1
                out.append(f'<blockquote>{self.blocks(chr(10).join(quote))[0]}</blockquote>')
            elif re.match(LIST_RE, line):
                ordered = bool(re.match(r'\s*\d+\.', line))
                items = []
                while i < len(lines) and (re.match(LIST_RE, lines[i]) or (re.match(r'\s{2,}\S', lines[i]) and items)):
                    if re.match(LIST_RE, lines[i]):
                        items.append(re.sub('^' + LIST_RE, '', lines[i]))
                    else:
                        items[-1] += ' ' + lines[i].strip()
                    i += 1
                tag = 'ol' if ordered else 'ul'
                out.append(f'<{tag}>' + ''.join(f'<li>{self.inline(it)}</li>' for it in items) + f'</{tag}>')
            elif re.match(r'\|.*\|\s*$', line) and re.match(r'\|?\s*:?-{3,}', lines[i + 1] if i + 1 < len(lines) else ''):
                def row(l):
                    return [c.strip() for c in re.sub(r'^\||\|$', '', l.strip()).split('|')]
                head = row(line)
                i += 2
                body = []
                while i < len(lines) and re.match(r'\|.*\|\s*$', lines[i]):
                    body.append(row(lines[i]))
                    i += 1
                out.append('<table><thead><tr>' + ''.join(f'<th>{self.inline(c)}</th>' for c in head) + '</tr></thead><tbody>'
                           + ''.join('<tr>' + ''.join(f'<td>{self.inline(c)}</td>' for c in r) + '</tr>' for r in body)
                           + '</tbody></table>')
            else:
                para = [lines[i].strip()]
                i += 1
                while (i < len(lines) and lines[i].strip()
                       and not re.match(r'(#{2,4}\s|```|>|\s*([-*]|\d+\.)\s+|\|.*\|\s*$)', lines[i])):
                    para.append(lines[i].strip())
                    i += 1
                out.append(f'<p>{self.inline(" ".join(para))}</p>')
        return '\n'.join(out), headings

    def footnotes(self):
        unused = [fid for fid in self.defs if fid not in self.order]
        missing = [fid for fid in self.order if fid not in self.defs]
        items = []
        for idx, fid in enumerate(self.order):
            n = idx + 1
            text = self.inline(self.defs[fid]) if fid in self.defs else '<mark class="podglad-luka">[brak definicji przypisu]</mark>'
            backs = ''.join(
                f'<a data-footnote-backref class="data-footnote-backref" aria-label="Wróć do miejsca w tekście (przypis {n})" '
                f'href="#user-content-fnref-{esc(fid)}{f"-{k + 1}" if k else ""}">↩{f"<sup>{k + 1}</sup>" if k else ""}</a>'
                for k in range(self.ref_count[fid])
            )
            items.append(f'<li id="user-content-fn-{esc(fid)}"><p>{text} {backs}</p></li>')
        for fid in unused:
            items.append(f'<li id="user-content-fn-{esc(fid)}"><p><mark class="podglad-luka">[brak odwołania w tekście: {esc(fid)}]</mark> '
                         f'{self.inline(self.defs[fid], refs=False)}</p></li>')
        return {'count': len(self.order) + len(unused), 'items': ''.join(items), 'missing': missing, 'unused': unused}


# ---------- podział szkicu ----------

def split_draft(body):
    defs, kept = {}, []
    lines = re.split(r'\r?\n', body)
    i = 0
    while i < len(lines):
        m = re.match(r'\[\^([^\]]+)\]:\s*(.*)$', lines[i])
        if m:
            text = m.group(2)
            while i + 1 < len(lines) and re.match(r'\s{2,}\S', lines[i + 1]):
                i += 1
                text += ' ' + lines[i].strip()
            defs[m.group(1)] = text
        else:
            kept.append(lines[i])
        i += 1
    # sekcje specjalne: „Propozycje ilustracji” i „Dla redakcji” nie są częścią artykułu
    special, main, current = {}, [], None
    for line in kept:
        h = re.match(r'##\s+(.*)$', line)
        if h:
            name = re.sub(r'\s*←.*$', '', h.group(1)).strip()
            current = name if name in (ILLUSTRATIONS, EDITORS) else None
            if current:
                special[current] = []
                continue
        (special[current] if current else main).append(line)
    return defs, '\n'.join(main), '\n'.join(special.get(ILLUSTRATIONS, [])), '\n'.join(special.get(EDITORS, []))


# ---------- pomocnicze do HTML wzoru ----------

def layout_error(what):
    fail(f'Nie znaleziono w układzie strony: {what}. Układ strony mógł się zmienić — zgłoś to na '
         f'kontakt@zarobkilekarzy.pl albo podaj inny wzór przez --wzor.')


def replace_once(html, pattern, fn, what):
    out, n = re.subn(pattern, fn, html, count=1)
    if not n:
        layout_error(what)
    return out


def element_range(html, start, tag):
    """Zakres elementu od otwierającego tagu (indeks) do jego zamknięcia, z liczeniem zagnieżdżeń."""
    depth = 0
    for m in re.compile(rf'<{tag}\b|</{tag}>').finditer(html, start):
        depth += -1 if m.group(0).startswith('</') else 1
        if depth == 0:
            return start, m.end()
    fail(f'Nie udało się odczytać elementu <{tag}> we wzorze.')


def attrs_of(tag_html):
    return ''.join(re.findall(r'\sdata-astro-cid-[\w-]+(?:="[^"]*")?', tag_html))


def fetch(url, optional=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'zarobkilekarzy-writer-podglad'})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.read()
    except urllib.error.HTTPError as err:
        if err.code == 404 and optional:
            return None
        fail(f'Nie udało się pobrać {url} (HTTP {err.code}).')
    except urllib.error.URLError as err:
        reason = err.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            fail('Python nie ma zainstalowanych certyfikatów SSL. Na macOS uruchom „Install Certificates.command” '
                 'z folderu Pythona w Aplikacjach i spróbuj ponownie.')
        fail(f'Brak połączenia z {SITE} ({reason}). Podgląd potrzebuje internetu — sprawdź połączenie i spróbuj ponownie.')
    except OSError as err:
        fail(f'Brak połączenia z {SITE} ({err}). Podgląd potrzebuje internetu — sprawdź połączenie i spróbuj ponownie.')


def inline_fonts(css):
    font_re = r'url\("?(/_astro/fonts/[^")]+)"?\)'
    urls = sorted(set(re.findall(font_re, css)))
    data = {}

    def load(u):
        try:
            req = urllib.request.Request(SITE + u, headers={'User-Agent': 'zarobkilekarzy-writer-podglad'})
            with urllib.request.urlopen(req, timeout=30) as res:
                data[u] = 'data:font/woff2;base64,' + base64.b64encode(res.read()).decode('ascii')
        except OSError:
            pass  # bez tego fontu podgląd użyje kroju zastępczego

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(load, urls))
    css = re.sub(font_re, lambda m: f'url("{data.get(m.group(1)) or SITE + m.group(1)}")', css)
    return re.sub(r'url\("?(/[^")]+)"?\)', lambda m: f'url("{SITE}{m.group(1)}")', css)


# ---------- składanie ----------

def main():
    input_path, template_url = parse_args(sys.argv[1:])
    try:
        with open(input_path, encoding='utf-8-sig') as f:
            src = f.read()
    except OSError as err:
        fail(f'Nie mogę odczytać pliku {input_path} ({err.strerror}).')

    data, body = parse_frontmatter(src)
    defs, draft_main, draft_illustrations, draft_editors = split_draft(body)
    r = Renderer(defs)
    warnings = []

    category = str(data.get('category') or '').strip()
    category_key = next((k for k in SECTIONS if k.lower() == category.lower()), None)
    if not category_key:
        warnings.append(f'Nieznana kategoria „{category}” — dozwolone: {", ".join(SECTIONS)}. W podglądzie: Analiza.')
    section = SECTIONS[category_key or 'Analiza']
    title = re.sub(r'\.\s*$', '', str(data.get('title') or ''))
    summary = data.get('summary') or ''
    key_points = data['keyPoints'] if isinstance(data.get('keyPoints'), list) else []

    # kolejność renderowania = kolejność czytania, żeby numery przypisów szły od góry strony
    title_html = r.inline(title) if title else '<mark class="podglad-luka">[brak title]</mark>'
    lead_html = r.inline(summary) if summary else '<mark class="podglad-luka">[brak summary]</mark>'
    points_html = [r.inline(k) for k in key_points]
    content_html, headings = r.blocks(draft_main)
    illustrations = r.blocks(draft_illustrations)[0] if draft_illustrations.strip() else ''
    notes = r.footnotes()
    editors = Renderer({}).blocks(draft_editors)[0] if draft_editors.strip() else ''

    words = len(re.sub(r'\[\^[^\]]+\]', '', draft_main).split())
    minutes = max(1, round(words / 200))
    today = datetime.date.today()
    iso_date, pl_date = today.isoformat(), today.strftime('%d.%m.%Y')
    gaps = len(re.findall(GAP_RE, src))

    html = None
    for url in [template_url] if template_url else DEFAULT_TEMPLATES:
        raw = fetch(url, optional=not template_url)
        if raw:
            html = raw.decode('utf-8')
            break
    if not html:
        fail(f'Nie znaleziono szablonu podglądu na {SITE}.')

    # <head>: bez skryptów zewnętrznych, preloadów i metadanych wzoru; style z osadzonymi fontami
    head_open = re.search(r'<head\b[^>]*>', html)
    head_end = html.find('</head>')
    if not head_open or head_end < 0:
        layout_error('<head>')
    head_start = head_open.start()
    styles = re.findall(r'<style[^>]*>[\s\S]*?</style>', html[head_start:head_end])
    css = inline_fonts('\n'.join(styles))
    head = (
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta name="robots" content="noindex"><title>Podgląd: {esc(title or "szkic")}</title>'
        f'<meta name="color-scheme" content="light dark">{css}'
        '''<style>
    .podglad-pasek{position:sticky;top:0;z-index:9999;background:#b45309;color:#fff;font:600 14px/1.4 system-ui,sans-serif;padding:8px 16px}
    .podglad-pasek details{font-weight:400;margin-top:4px}
    .podglad-pasek summary{cursor:pointer}
    .podglad-pasek .podglad-redakcja{background:#fff;color:#111;padding:8px 12px;margin-top:6px;max-height:40vh;overflow:auto}
    mark.podglad-luka{background:#fde68a;color:#111;padding:0 2px}
  </style>'''
    )
    html = html[:head_start] + f'<head>{head}' + html[head_end:]

    # usuń wszystkie skrypty i odnośniki względne zamień na adresy strony
    html = re.sub(r'<script\b[\s\S]*?</script>', '', html)
    html = re.sub(r'(href|src)="/(?!/)', lambda m: f'{m.group(1)}="{SITE}/', html)

    # <main>: zostaje tylko sekcja artykułu (bez „Powiązanych” i ramki postulatu wzoru)
    main_match = re.search(r'<main\b', html)
    if not main_match:
        layout_error('<main>')
    main_start = main_match.start()
    _, main_end = element_range(html, main_start, 'main')
    main_open = html[main_start:html.index('>', main_start) + 1]
    section_match = re.compile(r'<section\b').search(html, main_start)
    if not section_match:
        layout_error('sekcja artykułu')
    article_start = section_match.start()
    _, article_end = element_range(html, article_start, 'section')
    article = html[article_start:article_end]

    # Dopasowania tolerują odstępy między tagami, dodatkowe klasy i atrybuty.
    S = r'\s*'

    def cls(name):
        return rf'class="[^"]*\b{name}\b[^"]*"'

    # okruszki: drugi element = dział, ostatni = tytuł
    article = replace_once(article, rf'(<nav[^>]*{cls("crumbs")}[\s\S]*?<li[^>]*>{S}<a[^>]*>[^<]*</a>{S}</li>{S}<li[^>]*>{S}<a href=")[^"]*("[^>]*>)[^<]*(</a>)',
                           lambda m: f'{m.group(1)}{SITE}{section["href"]}{m.group(2)}{section["label"]}{m.group(3)}', 'okruszki')
    article = replace_once(article, rf'(<nav[^>]*{cls("crumbs")}[\s\S]*?<span[^>]*aria-current="page"[^>]*>)[^<]*(</span>)',
                           lambda m: f'{m.group(1)}{esc(title or "Szkic")}{m.group(2)}', 'okruszki')
    # nadtytuł, tytuł, lead
    article = replace_once(article, rf'(<p[^>]*{cls("eyebrow")}[^>]*>{S}<span[^>]*{cls("eyebrow__sq")}[^>]*>{S}</span>)[^<]*',
                           lambda m: m.group(1) + section['label'], 'nadtytuł')
    article = replace_once(article, rf'(<h1[^>]*>)[\s\S]*?(<span[^>]*{cls("dot")}|</h1>)', lambda m: m.group(1) + title_html + m.group(2), 'tytuł')
    article = replace_once(article, rf'(<p[^>]*{cls("ahead__lead")}[^>]*>)[\s\S]*?(</p>)', lambda m: m.group(1) + lead_html + m.group(2), 'lead')
    # metryczka
    article = replace_once(article, rf'(<dt[^>]*>{S}Aktualizacja{S}</dt>{S}<dd[^>]*>{S}<time[^>]*datetime=")[^"]*("[^>]*>)[^<]*',
                           lambda m: f'{m.group(1)}{iso_date}{m.group(2)}{pl_date}', 'data')
    article = re.sub(rf'(<dt[^>]*>{S}Czas czytania{S}</dt>{S}<dd[^>]*>)[^<]*', lambda m: f'{m.group(1)}{minutes} min', article, count=1)
    article = re.sub(rf'(<dt[^>]*>{S}Przypisy{S}</dt>{S}<dd[^>]*>){S}<a[^>]*>[^<]*</a>',
                     lambda m: m.group(1) + (f'<a href="#przypisy">{notes["count"]} ze źródłami</a>' if notes['count']
                                             else '<mark class="podglad-luka">[brak przypisów]</mark>'), article, count=1)

    # W skrócie
    def key_points_block(m):
        open_tag, items, close = m.group(1), m.group(2), m.group(3)
        li = (re.search(r'<li[^>]*>', items) or [None])[0] or '<li>'
        num = (re.search(r'<span[^>]*class="[^"]*\bnum\b[^"]*"[^>]*>', items) or [None])[0] or '<span class="num num--sm">'
        inner = re.search(r'<span[^>]*class="[^"]*\bnum\b[^"]*"[^>]*>\s*\d+\s*<span([^>]*)>', items)
        num_inner = inner.group(1) if inner else ''
        p = (re.search(r'<p[^>]*>', items) or [None])[0] or '<p>'
        if points_html:
            body = ''.join(f'{li}{num}{idx + 1:02d}<span{num_inner}>.</span></span>{p}{k}</p></li>' for idx, k in enumerate(points_html))
        else:
            body = f'{li}{p}<mark class="podglad-luka">[brak keyPoints]</mark></p></li>'
        return open_tag + body + close
    article = replace_once(article, rf'(<aside[^>]*{cls("ahead__points")}[\s\S]*?<ol[^>]*>)([\s\S]*?)(</ol>)', key_points_block, '„W skrócie”')

    # spis treści (bez odwołań do przypisów — te są już w nagłówkach treści)
    def toc_block(m):
        open_tag, items, close = m.group(1), m.group(2), m.group(3)
        li = (re.search(r'<li[^>]*>', items) or [None])[0] or '<li>'
        a = attrs_of((re.search(r'<a[^>]*>', items) or [''])[0])
        return open_tag + ''.join(f'{li}<a href="#{h["id"]}"{a}>{r.inline(h["text"], refs=False)}</a></li>' for h in headings) + close
    article = re.sub(r'(<zl-toc[\s\S]*?<ol[^>]*>)([\s\S]*?)(</ol>)', toc_block, article, count=1)

    # treść i przypisy
    prose_match = re.search(r'<div[^>]*class="[^"]*\bprose\b', article)
    if not prose_match:
        layout_error('treść artykułu (.prose)')
    prose_start = prose_match.start()
    _, prose_end = element_range(article, prose_start, 'div')
    prose_open = article[prose_start:article.index('>', prose_start) + 1]
    prose_old = article[prose_start:prose_end]
    aside_open = (re.search(r'<aside[^>]*class="[^"]*\baside--note\b[^"]*"[^>]*>', prose_old) or [None])[0]
    aside_cid = attrs_of(aside_open or '')
    foot_head = (re.search(r'<details[^>]*class="[^"]*\bfootnotes\b[^"]*"[\s\S]*?</summary>', prose_old) or [None])[0]
    prose = content_html
    if illustrations:
        if aside_open:
            prose += (f'{aside_open}<p class="aside__label"{aside_cid}>Dla redakcji</p><p class="aside__title"{aside_cid}>{ILLUSTRATIONS}</p>'
                      f'<div class="aside__body"{aside_cid}>{illustrations}</div></aside>')
        else:
            prose += f'<blockquote><p><strong>{ILLUSTRATIONS}</strong></p>{illustrations}</blockquote>'
    if notes['count']:
        if foot_head:
            summary_html = re.sub(r'(Przypisy\s*<span>)\d+(</span>)', lambda m: f'{m.group(1)}{notes["count"]}{m.group(2)}', foot_head, count=1)
        else:
            summary_html = f'<details class="footnotes" id="przypisy"><summary>Przypisy {notes["count"]}</summary>'
        prose += f'{summary_html}<ol>{notes["items"]}</ol></details>'
    article = article[:prose_start] + prose_open + prose + '</div>' + article[prose_end:]

    if not title or not summary or not key_points:
        warnings.append('Brakuje title, summary albo keyPoints — w podglądzie oznaczone na żółto.')
    if len(key_points) > 4:
        warnings.append(f'„W skrócie” ma {len(key_points)} punktów (najwyżej 4).')
    if notes['missing']:
        warnings.append(f'Odwołania do przypisów bez definicji: {", ".join(notes["missing"])}.')
    if notes['unused']:
        warnings.append(f'Przypisy bez odwołania w tekście: {", ".join(notes["unused"])}.')

    banner = (
        f'<div class="podglad-pasek" role="note">Podgląd lokalny szkicu — nieopublikowane · {esc(os.path.basename(input_path))} · '
        f'{words} słów · luk do uzupełnienia: {gaps}'
        + ''.join(f'<br>Uwaga: {esc(w)}' for w in warnings)
        + (f'<details><summary>Dla redakcji</summary><div class="podglad-redakcja">{editors}</div></details>' if editors else '')
        + '</div>'
    )

    html = html[:main_start] + main_open + article + '</main>' + html[main_end:]
    html = re.sub(r'<body([^>]*)>', lambda m: f'<body{m.group(1)}>{banner}', html, count=1)

    out_file = re.sub(r'\.md$', '', input_path, flags=re.IGNORECASE) + '.podglad.html'
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Zapisano podgląd: {os.path.abspath(out_file)}')
    for w in warnings:
        print(f'Uwaga: {w}')


if __name__ == '__main__':
    main()
