# zarobkilekarzy-writer-kit

Skill dla **Claude Code** i **OpenAI Codex**: asystent autora, który chce zaproponować tekst serwisowi
[zarobkilekarzy.pl](https://zarobkilekarzy.pl) — **artykuł na stronę** albo **gościnny wpis na X**
(@ZarobkiLekarzy).

Dla kogo: dla osób, które mają coś ważnego do powiedzenia o publicznych pieniądzach w ochronie zdrowia,
ale nie lubią pisać albo nie mają wprawy. Mówisz agentowi swoimi słowami, co wiesz i co myślisz, a on
pomaga to ułożyć w tekst zgodny z zasadami redakcyjnymi serwisu.

## Co robi skill

- zadaje pytania i pomaga sformułować **tezę jednym zdaniem**;
- rozbija Twój materiał na twierdzenia i sprawdza, czy **każde ma źródło** (fakt, szacunek, zarzut, opinia);
- proponuje **szkielet** artykułu albo wątku i układa w nim **Twoje zdania**, z przypisami;
- pilnuje **głosu**: spokojnie, rzeczowo, mechanizm → liczba → źródło → granice, bez nazwisk;
- wyłapuje typowe **pułapki liczb** (umowa ≠ osoba, plan ≠ wykonanie, przychód ≠ dochód);
- gdy się gubisz — **zatrzymuje się, porządkuje i proponuje kolejne kroki**;
- pokazuje **podgląd artykułu w wyglądzie zarobkilekarzy.pl** (lokalny plik HTML ze stylami strony)
  i **podgląd wpisu albo wątku na X** z konta @ZarobkiLekarzy, z licznikiem znaków jak na X;
- na koniec przygotowuje **plik do wysłania mailem** z notatką dla redakcji.

**Skill jest asystentem, nie autorem.** Układa, poprawia i sprawdza — nie dopisuje tez, argumentów ani
liczb, których nie podałeś. Gdy czegoś brakuje, zapyta.

## Instalacja (skopiuj i wklej agentowi)

Otwórz Claude Code albo Codex i wklej:

```text
Zainstaluj skill „zarobkilekarzy-writer” z repozytorium
https://github.com/zarobkilekarzy/zarobkilekarzy-writer-kit

1. Ustal, którym agentem jesteś, i wybierz katalog skilli osobistych:
   - Claude Code: ~/.claude/skills/
   - OpenAI Codex: ~/.agents/skills/ (starsze wersje: ~/.codex/skills/) — sprawdź w dokumentacji
     swojej wersji, który katalog czyta.
   Jeśli nie masz pewności, zapytaj mnie, zanim cokolwiek skopiujesz.
2. Pobierz repozytorium do katalogu tymczasowego (git clone --depth 1 albo archiwum ZIP z GitHuba).
3. Skopiuj CAŁY folder „zarobkilekarzy-writer” (SKILL.md oraz katalogi references/ i scripts/) do katalogu
   skilli, tak żeby powstała ścieżka <katalog skilli>/zarobkilekarzy-writer/SKILL.md.
   Jeśli taki folder już istnieje — pokaż mi różnice i zapytaj, czy nadpisać.
4. Niczego teraz nie uruchamiaj. Skrypty podglądu artykułu i wpisu na X (scripts/*.mjs dla Node 18+
   albo scripts/*.py dla Pythona 3.8+, bez zależności) skill uruchamia później, gdy poproszę o podgląd.
   Sprawdź tylko, czy mam Node (node --version) albo Pythona (python3 --version, w Windows: py --version),
   i powiedz mi, jeśli nie ma żadnego z nich.
5. Usuń katalog tymczasowy.
6. Potwierdź instalację: podaj pełną ścieżkę do SKILL.md, przeczytaj go i streść mi w 3 zdaniach,
   jak będziesz mi pomagać. Powiedz, czy trzeba uruchomić Cię ponownie, żeby skill był widoczny.
```

Instalacja ręczna: pobierz repozytorium i skopiuj folder `zarobkilekarzy-writer/` do katalogu skilli
z punktu 1.

## Jak zacząć

Po instalacji otwórz nową rozmowę w pustym folderze (tam agent zapisze plik tekstu) i napisz na przykład:

- *„Chcę napisać artykuł dla zarobkilekarzy.pl o tym, jak mój szpital rozlicza dyżury. Pomóż mi.”*
- *„Mam notatki o kolejkach do endokrynologa — zróbmy z tego wpis na X dla @ZarobkiLekarzy.”*
- *„Sprawdź mój szkic artykułu pod kątem źródeł i liczb.”* (i wklej tekst albo podaj plik)
- *„Pogubiłem się, co dalej?”*

W Claude Code skill możesz też wywołać wprost: `/zarobkilekarzy-writer`.

## Podgląd artykułu

Poproś agenta: *„Pokaż podgląd”*. Agent uruchomi skrypt podglądu (w Node albo w Pythonie — wystarczy jedno
z nich, wynik jest ten sam). Skrypt pobiera z zarobkilekarzy.pl
szablon podglądu z układem artykułu (style i fonty), wstawia w niego Twój tekst i zapisuje obok szkicu plik
`….podglad.html` do otwarcia w przeglądarce. Luki do uzupełnienia są w nim zaznaczone na żółto.
Ręcznie:

```bash
node ~/.claude/skills/zarobkilekarzy-writer/scripts/podglad.mjs artykul-temat.md
```

```bash
python3 ~/.claude/skills/zarobkilekarzy-writer/scripts/podglad.py artykul-temat.md
```

(w Codexie ścieżka do katalogu skilli jest inna). Podgląd to tylko widok dla Ciebie — do maila dołącz
plik `.md`.

## Podgląd wpisu na X

Poproś agenta: *„Pokaż podgląd wpisu”*. Zobaczysz wpis albo wątek tak, jak na osi czasu X na koncie
@ZarobkiLekarzy (tryb jasny i ciemny), z licznikiem znaków liczonym jak na X i ostrzeżeniami: za długi wpis,
wykrzyknik, oznaczenie konta, liczba bez linku do źródła. Ręcznie:

```bash
node ~/.claude/skills/zarobkilekarzy-writer/scripts/podglad-x.mjs x-temat.md
```

```bash
python3 ~/.claude/skills/zarobkilekarzy-writer/scripts/podglad-x.py x-temat.md
```

## Wysyłka

Gotowy plik (`artykul-….md` albo `x-….md`) z notatką „Dla redakcji” wyślij mailem na
**kontakt@zarobkilekarzy.pl** jako załącznik. Poproś agenta: *„Przygotuj wysyłkę”* — sprawdzi format pliku,
powie, co dołączyć, i napisze gotowy mail do skopiowania. Nie potrzebujesz konta na GitHubie ani niczego publikować. O publikacji
decyduje redakcja; może odpisać z pytaniami albo poprawkami.

## Zawartość

```
zarobkilekarzy-writer/
├── SKILL.md                     # rola asystenta, przebieg pracy, zasady, których agent nie łamie
├── scripts/
│   ├── podglad.mjs              # podgląd artykułu w wyglądzie strony (Node 18+, bez zależności)
│   ├── podglad.py               # to samo w Pythonie 3.8+ (tylko biblioteka standardowa)
│   ├── podglad-x.mjs            # podgląd wpisu albo wątku na X z konta @ZarobkiLekarzy (Node 18+)
│   ├── podglad-x.py             # to samo w Pythonie 3.8+
│   └── avatar-x.png             # avatar konta do podglądu wpisu
└── references/
    ├── formaty.md               # artykuł na stronę i wpis na X: wymagania i szablony plików
    ├── rzetelnosc.md            # źródła, statusy twierdzeń, nazwiska, prawo cytatu, sprostowania
    ├── styl.md                  # głos, rytm, zapis, przykłady „przed → po”
    ├── liczby.md                # pytania do każdej liczby, pułapki mierników, gdzie są aktualne dane
    ├── zrodla.md                # zarobkilekarzy.pl i źródła pierwotne: prawo, NFZ, GUS, NIL, OECD…
    ├── gdy-sie-gubisz.md        # sygnały, techniki porządkowania, następne kroki, zachęty
    └── wysylka.md               # kontrola formatu, załączniki, gotowy mail do redakcji
```

## Zasady w pigułce

1. Każda teza ma ogólnodostępne źródło (link). Prawo i wyroki — tylko teksty pierwotne.
2. Fakt ≠ szacunek ≠ zarzut ≠ opinia — i tekst to mówi.
3. Liczby dokładne, z jednostką i rokiem; bez zaokrąglania w stronę sensacji.
4. Mechanizmy, nie osoby: bez nazwisk.
5. Przeciwnikiem jest nieprzejrzystość, nie zawód lekarza.
6. Spokojny głos: objaśniamy, nie polemizujemy.

## Licencja

Treść skilla: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pl) — możesz ją kopiować
i zmieniać, podając źródło: zarobkilekarzy.pl.

Uwagi do skilla: kontakt@zarobkilekarzy.pl.
