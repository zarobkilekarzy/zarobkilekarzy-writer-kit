# Wysyłka do redakcji

Autor wysyła tekst mailem na **kontakt@zarobkilekarzy.pl**. Ty niczego nie wysyłasz — przygotowujesz pliki,
sprawdzasz format i piszesz gotowy mail do skopiowania. Przejdź tę listę po kolei i powiedz autorowi,
co jest gotowe, a co jeszcze wymaga jego decyzji.

## 1. Plik tekstu

| Format | Nazwa pliku | Wzór |
|---|---|---|
| Artykuł | `artykul-<krotki-temat>.md` | `formaty.md`, część A |
| Wpis na X | `x-<krotki-temat>.md` | `formaty.md`, część B |

`<krotki-temat>`: małe litery bez polskich znaków, słowa łączone myślnikiem (np. `artykul-dyzury-w-powiecie.md`).
Kodowanie UTF-8. Jeden tekst = jeden plik.

## 2. Kontrola formatu — artykuł

Sprawdź w pliku (a jeśli robiłeś podgląd — przejrzyj ostrzeżenia skryptu, bo sprawdza część z tych rzeczy sam):

- [ ] Nagłówek YAML zaczyna się i kończy linią `---`.
- [ ] Jest `title` — bez kropki na końcu.
- [ ] `category` to dokładnie jedno z: `Mechanizm`, `Dane`, `Analiza`, `Przewodnik`.
- [ ] Jest `summary` — 1–2 zdania, pierwsze do ok. 120 znaków.
- [ ] `keyPoints` ma 3, najwyżej 4 punkty, każdy z jedną liczbą.
- [ ] Śródtytuły to `##` (poziom niżej: `###`); tytuł jest tylko w `title`, bez `#` w treści.
- [ ] Każde `[^id]` w tekście ma definicję `[^id]: …` na końcu i każda definicja jest użyta.
- [ ] Identyfikatory przypisów są opisowe (`[^nfz-plan-2026]`), bez spacji.
- [ ] Każdy przypis ma wydawcę, tytuł z linkiem i datę.
- [ ] W treści nie ma linków do źródeł — źródła są tylko w przypisach (linki do innych stron
      zarobkilekarzy.pl są w porządku).
- [ ] Sekcje `## Propozycje ilustracji` (jeśli są) i `## Dla redakcji` mają dokładnie takie nazwy i stoją
      na końcu, przed definicjami przypisów albo po nich.
- [ ] Usunięte są dopiski z szablonu („← opcjonalnie…”) i puste sekcje.
- [ ] Wszystkie luki (`[ŹRÓDŁO?]`, `[DO SPRAWDZENIA]`, `[PYTANIE]`) albo zostały uzupełnione, albo są
      wypisane w „Dla redakcji” jako otwarte.

## 3. Kontrola formatu — wpis na X

- [ ] Każdy wpis ma nagłówek `## Wpis n/N` i licznik znaków; żaden nie przekracza 280 (link = 23 znaki).
      Najprościej sprawdzić to podglądem wpisu na X — pokazuje licznik i ostrzeżenia.
- [ ] Pierwszy wpis działa sam.
- [ ] We wpisach nie ma linków do źródeł ani dopisków „Źródło: …”.
- [ ] Każda liczba i teza ma źródło w `## Podkładka`, z numerem wpisu („Wpis 2 — …”).
- [ ] Nie ma oznaczeń osób (`@…`), nazwisk ani wykrzykników.

## 4. Sekcja „Dla redakcji”

Na końcu pliku, pod nagłówkiem `## Dla redakcji`:

```markdown
## Dla redakcji

- Sprawdzone w oryginale: przypisy nfz-plan-2026, aotmit-mediany (otwarte PDF-y, tabele 2 i 4).
- Do sprawdzenia: przypis gus-kadry — link działał, ale liczby nie znalazłem w tabeli.
- Otwarte pytania: czy podawać nazwę województwa (przykład z dyżurem)?
- Związek autora z tematem: pielęgniarka w szpitalu powiatowym; tekst o własnym szpitalu, bez danych osób.
- Ilustracje: dane do wykresu w pliku dane-dyzury.csv.
- Parking (pomysły na inne teksty): …
```

To notatka dla redakcji, nie część tekstu — redakcja jej nie publikuje.

## 5. Załączniki

- **Dołącz:** plik `.md`; ewentualnie dane do proponowanych wykresów (CSV albo tabela w pliku) i własne zdjęcia.
- **Zdjęcia:** tylko własne albo z jasną licencją; przed wysłaniem usuń metadane (EXIF: autor, GPS,
  urządzenie). Na macOS: Podgląd → Narzędzia → Pokaż inspektora → usuń dane lokalizacji, albo wyślij zrzut
  zdjęcia zamiast oryginału.
- **Nie dołączaj:** pliku `.podglad.html` (to tylko widok dla autora), dokumentów z danymi osobowymi,
  skanów z nazwiskami. Jeśli źródłem jest dokument niedostępny w sieci (np. odpowiedź na wniosek
  o informację publiczną) — dołącz go z zamazanymi danymi osobowymi i opisz w „Dla redakcji”.

## 6. Mail

Przygotuj autorowi gotowy tekst do skopiowania:

```text
Do: kontakt@zarobkilekarzy.pl
Temat: Propozycja artykułu: <tytuł>          (albo: Propozycja wpisu na X: <temat>)

Dzień dobry,

przesyłam propozycję tekstu dla zarobkilekarzy.pl — w załączniku plik <nazwa pliku>.
<Jedno zdanie: o czym jest tekst i jaka jest jego teza.>

Otwarte punkty i informacje dla redakcji są na końcu pliku, w sekcji „Dla redakcji”.

<Podpis — tak, jak autor chce się przedstawić redakcji.>
```

Plik wysyła się jako **załącznik**, nie wklejony w treść maila (Markdown w treści maila się psuje).

## 7. Po wysyłce

Powiedz autorowi wprost:
- o publikacji decyduje redakcja; może odpisać z pytaniami albo poprawkami;
- poprawki najlepiej wprowadzać w tym samym pliku i odsyłać całość (z dopiskiem, co się zmieniło);
- warto zachować plik i notatki — parking to gotowe pomysły na kolejne teksty.
