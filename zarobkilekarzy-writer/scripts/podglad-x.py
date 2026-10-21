#!/usr/bin/env python3
# Podgląd wpisu albo wątku na X z konta @ZarobkiLekarzy — wersja w Pythonie (to samo co podglad-x.mjs).
#
# Czyta plik x-<temat>.md (formaty.md, część B) i zapisuje obok plik HTML z wpisami tak, jak na osi czasu X:
# avatar i nazwa konta, tekst z linkami, karta linku do zarobkilekarzy.pl, licznik znaków liczony jak na X,
# tryb jasny i ciemny obok siebie. Wymaga Pythona 3.8+; tylko biblioteka standardowa. Łączy się tylko
# z zarobkilekarzy.pl (karta linku); bez internetu podgląd powstaje bez karty.
#
# Użycie: python3 podglad-x.py x-temat.md

import base64
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, 'reconfigure'):
    # konsola Windows bez UTF-8 wywraca się na polskich znakach
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SITE = (os.environ.get('PODGLAD_STRONA') or 'https://zarobkilekarzy.pl').rstrip('/')
ACCOUNT = {'name': 'zarobkilekarzy.pl', 'handle': '@ZarobkiLekarzy'}
LIMIT = 280
URL_LENGTH = 23
URL_RE = re.compile(r'https?://[^\s<>"]+[^\s<>".,;:!?)\]\'”]')
# emoji jako jawne zakresy (te same w podglad-x.mjs): flaga z dwóch liter regionalnych albo znak z modyfikatorami
EMOJI_BASE = '[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿]'
EMOJI_RE = re.compile(f'[\U0001F1E6-\U0001F1FF]{{2}}|{EMOJI_BASE}(?:️|[\U0001F3FB-\U0001F3FF]|‍{EMOJI_BASE})*')
UA = {'User-Agent': 'zarobkilekarzy-writer-podglad'}


def fail(msg):
    print(f'Błąd: {msg}', file=sys.stderr)
    sys.exit(1)


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# ---------- plik wpisu ----------

def parse_post(src):
    """Sekcje „## …”: wpisy („Wpis 1/N”), propozycja grafiki i notatka dla redakcji."""
    sections, current = [], None
    for line in re.split(r'\r?\n', src):
        h = re.match(r'##\s+(.*)$', line)
        if h:
            current = {'title': h.group(1).strip(), 'lines': []}
            sections.append(current)
        elif current:
            current['lines'].append(line)

    def text(s):
        return '\n'.join(s['lines']).strip() if s else ''

    def first(pattern):
        return next((s for s in sections if re.match(pattern, s['title'], re.IGNORECASE)), None)

    return {
        'posts': [text(s) for s in sections if re.match(r'Wpis\b', s['title'], re.IGNORECASE)],
        'graphic': text(first(r'Propozycja grafiki')),
        'editors': text(first(r'Dla redakcji')),
    }


# ---------- licznik znaków jak na X ----------

def weighted_length(text):
    """
    Długość wpisu liczona jak na X (twitter-text, wersja 3): link = 23 znaki, emoji = 2, znaki z zakresów
    łacińskich (także polskie litery), myślniki i cudzysłowy typograficzne = 1, pozostałe = 2.
    """
    plain = URL_RE.sub('', unicodedata.normalize('NFC', text))
    n = len(URL_RE.findall(text)) * URL_LENGTH
    emoji = len(EMOJI_RE.findall(plain))
    n += emoji * 2
    for ch in EMOJI_RE.sub('', plain):
        c = ord(ch)
        light = c <= 0x10FF or 0x2000 <= c <= 0x200D or 0x2010 <= c <= 0x201F or 0x2032 <= c <= 0x2037
        n += 1 if light else 2
    return n


def display_url(url):
    """Adres w treści wpisu tak, jak pokazuje go X: bez protokołu i „www.”, ucięty po 23 znakach."""
    bare = re.sub(r'^https?://(www\.)?', '', url)
    return f'{bare[:23]}…' if len(bare) > 25 else bare


def render_text(text):
    stash = []

    def keep(html):
        stash.append(html)
        return f'\x00{len(stash) - 1}\x00'

    s = URL_RE.sub(lambda m: keep(f'<a class="link" href="{esc(m.group(0))}">{esc(display_url(m.group(0)))}</a>'), text)
    s = re.sub(r'(^|[^\w@])([@#]\w+)', r'\1<span class="link">\2</span>', esc(s))
    s = s.replace('\n', '<br>')
    return re.sub(r'\x00(\d+)\x00', lambda m: stash[int(m.group(1))], s)


# ---------- karta linku do zarobkilekarzy.pl ----------

def fetch_card(url):
    if not url.startswith(f'{SITE}/') and url != SITE:
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as res:
            html = res.read().decode('utf-8')

        def meta(prop):
            m = re.search(rf'<meta[^>]+property="og:{prop}"[^>]+content="([^"]*)"', html)
            return m.group(1) if m else None

        image, data = meta('image'), None
        if image:
            try:
                with urllib.request.urlopen(urllib.request.Request(image.replace('&amp;', '&'), headers=UA), timeout=30) as img:
                    data = f'data:{img.headers.get("Content-Type") or "image/png"};base64,' + base64.b64encode(img.read()).decode('ascii')
            except urllib.error.HTTPError:
                pass
        return {'url': url, 'title': meta('title'), 'image': data}
    except urllib.error.HTTPError as err:
        return {'url': url, 'error': f'HTTP {err.code}'}
    except (urllib.error.URLError, OSError) as err:
        return {'url': url, 'error': str(getattr(err, 'reason', err))}


# ---------- ostrzeżenia ----------

def check_post(text, i, total):
    w = []
    n = weighted_length(text)
    label = f'Wpis {i + 1}/{total}' if total > 1 else 'Wpis'
    if n > LIMIT:
        w.append(f'{label}: {n}/{LIMIT} znaków — za długi o {n - LIMIT}.')
    if not text.strip():
        w.append(f'{label}: pusty.')
    plain = URL_RE.sub('', text)
    if '!' in plain:
        w.append(f'{label}: wykrzyknik — głos serwisu jest bez wykrzykników.')
    if re.search(r'(^|[^\w])@\w', plain):
        w.append(f'{label}: oznaczenie konta (@…) — wpisy nie oznaczają osób.')
    if re.search(r'[0-9]', plain) and plain == text:
        w.append(f'{label}: liczba bez linku do źródła.')
    return w


# ---------- HTML ----------

ICONS = [
    'M2 11a7 7 0 0 1 7-7h6a7 7 0 0 1 0 14h-3l-5 4v-4.5A7 7 0 0 1 2 11z',  # odpowiedz
    'M5 7h11l-3-3M19 17H8l3 3M5 7v6M19 17v-6',  # podaj dalej
    'M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z',  # polub
    'M5 20V12M10 20V6M15 20v-9M20 20V9',  # wyświetlenia
    'M12 4v11M7 9l5-5 5 5M5 14v5h14v-5',  # udostępnij
]
ACTIONS = ''.join(f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{d}"/></svg>' for d in ICONS)


def render_post(text, i, total, avatar, card, graphic):
    n = weighted_length(text)
    if graphic and i == 0:
        media = f'<div class="graphic"><span>Propozycja grafiki</span>{render_text(graphic)}</div>'
    elif card and card.get('image'):
        host = esc(urllib.parse.urlsplit(card['url']).netloc)
        media = (f'<div class="card"><img src="{card["image"]}" alt=""><span class="card__domain">{host}</span></div>'
                 f'<p class="card__from">Z: {host}</p>')
    else:
        media = ''
    thread = ' post--thread' if i < total - 1 else ''
    over = ' post__count--over' if n > LIMIT else ''
    position = f'{i + 1}/{total} · ' if total > 1 else ''
    return f'''<article class="post{thread}">
  <div class="post__side"><img class="avatar" src="{avatar}" alt=""></div>
  <div class="post__main">
    <p class="post__head"><strong>{ACCOUNT['name']}</strong> <span>{ACCOUNT['handle']} · teraz</span></p>
    <div class="post__text">{render_text(text)}</div>
    {media}
    <div class="post__actions">{ACTIONS}</div>
    <p class="post__count{over}">{position}{n}/{LIMIT} znaków</p>
  </div>
</article>'''


def posts_word(n):
    """2–4, 22–24… wpisy; 5–21, 25… wpisów"""
    return 'wpisy' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'wpisów'


CSS = '''  * { box-sizing: border-box; }
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
'''


# ---------- składanie ----------

def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith('--'):
        fail('Podaj plik wpisu: python3 podglad-x.py x-temat.md')
    input_path = sys.argv[1]
    try:
        with open(input_path, encoding='utf-8-sig') as f:
            src = f.read()
    except OSError as err:
        fail(f'Nie mogę odczytać pliku {input_path} ({err.strerror}).')
    parsed = parse_post(src)
    posts, graphic, editors = parsed['posts'], parsed['graphic'], parsed['editors']
    if not posts:
        fail('Nie znalazłem żadnego wpisu. Każdy wpis zaczyna się od nagłówka „## Wpis 1/N” (formaty.md, część B).')

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, 'avatar-x.png'), 'rb') as f:
        avatar = 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')

    # X pokazuje kartę ostatniego linku we wpisie (gdy wpis nie ma grafiki)
    cards = []
    for p in posts:
        urls = URL_RE.findall(p)
        cards.append(fetch_card(urls[-1]) if urls else None)

    warnings = [w for i, p in enumerate(posts) for w in check_post(p, i, len(posts))]
    for c in cards:
        if c and c.get('error'):
            warnings.append(f'Nie udało się pobrać karty linku {c["url"]} ({c["error"]}) — podgląd bez obrazka.')

    def column(theme):
        label = 'Tryb jasny' if theme == 'light' else 'Tryb ciemny'
        return (f'<section class="col {theme}"><p class="col__label">{label}</p>'
                + ''.join(render_post(p, i, len(posts), avatar, cards[i], graphic) for i, p in enumerate(posts))
                + '</section>')

    name = esc(os.path.basename(input_path))
    count = '1 wpis' if len(posts) == 1 else f'wątek: {len(posts)} {posts_word(len(posts))}'
    notes = ''.join(f'<br>Uwaga: {esc(w)}' for w in warnings)
    notes += f'<details><summary>Dla redakcji</summary><div class="notes">{esc(editors)}</div></details>' if editors else ''
    html = f'''<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Podgląd wpisu na X: {name}</title>
<style>
{CSS}</style>
</head>
<body>
<div class="bar" role="note">Podgląd lokalny wpisu na X — nieopublikowane · {name} · {count}{notes}</div>
<main class="cols">{column('light')}{column('dark')}</main>
</body>
</html>
'''

    out_file = re.sub(r'\.md$', '', input_path, flags=re.IGNORECASE) + '.podglad.html'
    with open(out_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)
    print(f'Zapisano podgląd: {os.path.abspath(out_file)}')
    for w in warnings:
        print(f'Uwaga: {w}')


if __name__ == '__main__':
    main()
