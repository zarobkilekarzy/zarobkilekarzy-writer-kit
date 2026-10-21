# Formaty: artykuł na stronę i wpis gościnny na X

Redakcja przyjmuje dwa formaty. W obu obowiązują te same zasady rzetelności i głosu. Szablon to
rusztowanie, nie formularz — sekcje artykułu można łączyć, ale kolejność „mechanizm → liczba → źródło →
granice” zostaje.

## A. Artykuł na zarobkilekarzy.pl

**Czym jest:** tekst objaśniający jeden mechanizm, jedno zjawisko albo jeden zbiór danych — od podstaw,
dla czytelnika, który nie zna tematu. Wzory: dowolny tekst z https://zarobkilekarzy.pl/llms.txt
(np. https://zarobkilekarzy.pl/mechanizmy/kontrakt-vs-etat/).

**Długość:** artykuły na stronie mają zwykle 1500–2500 słów (najkrótsze ok. 700, najdłuższe ok. 4000).
Długość wynika z tematu — lepszy krótki tekst z jedną tezą niż długi z pięcioma.

**Kategorie:** `Mechanizm` (jak działa system), `Dane` (zbiór liczb i co z nich wynika), `Analiza`
(porównanie, przypadek, przegląd), `Przewodnik` (instrukcja dla pacjenta lub czytelnika).

### Szablon pliku `artykul-<krotki-temat>.md`

```markdown
---
title: Tytuł-teza bez kropki na końcu
category: Mechanizm            # Mechanizm | Dane | Analiza | Przewodnik
summary: >-
  Lead: 1–2 zdania — problem i najważniejsza liczba. Pierwsze zdanie krótkie (do ok. 120 znaków).
keyPoints:                     # „W skrócie”: 3, najwyżej 4 punkty, każdy z jedną liczbą
  - …
  - …
  - …
stat: { value: "73%", unit: "czego dotyczy liczba" }   # opcjonalnie: jedna liczba na kartę w spisie
related:                       # opcjonalnie: powiązane teksty z zarobkilekarzy.pl
  - https://zarobkilekarzy.pl/…
---

Pierwszy akapit: scena albo konkretny przypadek (bez nazwisk), który pokazuje problem.[^zrodlo-1]

## Śródtytuł-teza bez kropki

Mechanizm → liczba → źródło → granice. Jeden akapit = jedna myśl.

## Śródtytuł-teza bez kropki

…

## Czego nie wiadomo

Granice danych: czego liczby nie pokazują, czego nikt nie zbiera, co mówi druga strona.

## Co z tego wynika            ← opcjonalnie; wyraźnie stanowisko autora, oddzielone od informacji

…

[^zrodlo-1]: Wydawca, [tytuł dokumentu](https://…), data, strona/tabela/punkt.

## Propozycje ilustracji        ← opcjonalnie

- **Teza ilustracji jednym zdaniem.** Co ma pokazać (np. słupki: Polska vs 4 kraje). Dane: tabela
  poniżej albo link. Źródło: …

## Dla redakcji

- Sprawdzone w oryginale: przypisy …
- Do sprawdzenia: …
- Związek autora z tematem: …
- Parking (pomysły na inne teksty): …
```

Uwagi:
- **Przypisy z nazwami** (`[^nfz-plan-2026]`), nie numerami — łatwiej je przenosić przy redakcji.
- **Wykresów i grafik autor nie robi** — opisuje je w „Propozycjach ilustracji” razem z danymi i źródłem.
  Grafikę przygotowuje redakcja w systemie wizualnym strony.
- **Zdjęcia** — tylko własne albo z jasną licencją, w osobnych plikach, z opisem i informacją o prawach.
  Przed wysłaniem usuń z nich metadane (EXIF: autor, GPS, urządzenie).
- Nie dodawaj podpisu, biogramu ani informacji o pomocy AI — redakcja ustala to z autorem w mailu.
- **Podgląd w wyglądzie strony** czyta pola z nagłówka (`title`, `category`, `summary`, `keyPoints`)
  i sekcje o dokładnie takich nazwach jak w szablonie — trzymaj się ich (`SKILL.md` → „Podgląd artykułu”).

## B. Wpis gościnny na X (@ZarobkiLekarzy)

**Czym jest:** krótki tekst do opublikowania na koncie serwisu — pojedynczy wpis albo wątek. Jedna liczba,
jeden mechanizm, jedno źródło. Często to dobry pierwszy krok przed artykułem.

**Limit:** licz **280 znaków na wpis** (link liczy się jako 23 znaki). Wątek: każdy wpis osobno w limicie;
najlepiej 3–6 wpisów.

**Zasady formatu:**
- pierwszy wpis musi działać sam — ktoś przeczyta tylko jego;
- 1 wpis = 1 myśl; liczba z jednostką i okresem;
- źródło przy liczbie (link do dokumentu albo do strony zarobkilekarzy.pl, gdzie jest przypis);
- bez oznaczania osób (`@nazwa`), bez nazwisk, bez wykrzykników i bez „🚨”;
- grafika — tylko opis propozycji (co pokazać, dane, źródło), wykonuje ją redakcja.

### Szablon pliku `x-<krotki-temat>.md`

```markdown
# Wpis na X: <temat w kilku słowach>

## Wpis 1/N  (xxx/280)
[Liczba z jednostką i okresem] — [co znaczy, jednym zdaniem].
[Mechanizm: dlaczego tak jest albo czego nie widać].
Źródło: https://…

## Wpis 2/N  (xxx/280)
…

## Propozycja grafiki   ← opcjonalnie
Teza jednym zdaniem; co pokazać; dane; źródło.

## Dla redakcji
- Sprawdzone w oryginale: …
- Do sprawdzenia: …
- Związek autora z tematem: …
```

Przy każdym wpisie podaj w nawiasie liczbę znaków — dokładną daje podgląd wpisu na X (`SKILL.md` →
„Podgląd wpisu na X”). Jeśli wpis przekracza limit — skróć słowa autora albo zaproponuj podział na dwa
wpisy; nie wyrzucaj po cichu źródła ani zastrzeżenia. Nagłówki `## Wpis n/N`, `## Propozycja grafiki`
i `## Dla redakcji` muszą mieć takie brzmienie — po nich podgląd rozpoznaje części pliku.
