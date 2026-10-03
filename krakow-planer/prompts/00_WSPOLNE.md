# Prompty: wspólne

Jak tego używać:
1. Blok KONTEKST wklejasz na początek KAŻDEGO promptu (albo wrzucasz do
   `CLAUDE.md` / `.cursorrules` / instrukcji repo, wtedy agent ma go zawsze).
2. Pliki `01_BACK.md` i `02_FRONT.md` zawierają prompty etapami dla obu osób.
3. `docs/CONTRACT.md` dajecie agentom jako plik w repo.
4. Na koniec każdego promptu dopisz linijkę:
   `Na końcu napisz, czego NIE zrobiłeś albo co zgadywałeś.`
   Agenci często po cichu zmieniają kontrakt albo coś zgadują, a ta linijka
   ujawnia to od razu.

---

## KONTEKST PROJEKTU (wklej zawsze)

```
Projekt: webowy planer wycieczek po Krakowie (tylko Kraków), hackathon.
Priorytet: działające demo/MVP, KISS, happy path, bez przeinżynierowania.
Stack: Next.js + TypeScript + Tailwind + shadcn + TanStack Query + lucide;
backend FastAPI (Python); mapy Leaflet + OpenStreetMap; routing OSRM
(darmowy); baza Supabase/PostgreSQL (na MVP może być seed z JSON-a).
Flow: formularz -> JSON do LLM (Ollama) -> konfiguracja -> algorytm trasy ->
odpowiedź JSON -> front rysuje atrakcje (markery) i trasę (polyline).
Źródło prawdy o formacie danych: docs/CONTRACT.md oraz mock_plan.json.
Zasady: nie zmieniaj kontraktu na własną rękę. Jeśli czegoś brakuje,
napisz mi, co proponujesz zmienić i dlaczego, zanim to zrobisz.
Pisz małe, czytelne zmiany. Po każdym zadaniu powiedz, co zrobiłeś
i jak to uruchomić/sprawdzić.
```

---

## FAZA 0: kontrakt (razem, ten sam prompt dla Back i Front)

```
Zadanie: przygotuj plik mock_plan.json zgodny z docs/CONTRACT.md.
Wymagania: 1 propozycja (label A, strategy cheapest), start + 4 atrakcje
w Krakowie (Rynek Główny, Wawel, Kazimierz, Planty itp.) + end;
legs z realistycznymi coords [lat,lng] (min. 5-10 punktów na leg),
mieszanka mode (walk, bus), jeden warning (np. TIME_EXCEEDED).
Zadbaj, żeby spełnione były wszystkie niezmienniki z kontraktu
(legs = stops-1, sumy w summary się zgadzają).
Na końcu wypisz krótką walidację niezmienników, które sprawdziłeś.
```

---

## FAZA 2: integracja (razem)

Back:
```
Zadanie: przetestuj POST /api/plan end-to-end na 3 scenariuszach:
(1) krótki czas, (2) mały budżet, (3) dużo atrakcji i wygodny budżet.
Dla każdego sprawdź niezmienniki z docs/CONTRACT.md skryptem walidującym
(napisz go: validate_plan(plan) -> lista naruszeń). Napraw naruszenia
w backendzie. Sprawdź, czy coords mieszczą się w zakresie Krakowa
(wykrywanie odwróconych współrzędnych). Zgłoś mi, jeśli kontrakt wymaga
zmiany - nie zmieniaj go sam.
```

Front:
```
Zadanie: przełącz aplikację z mocka na prawdziwy backend i przetestuj
te same 3 scenariusze. Sprawdź: czy polylines leżą na ulicach (nie w innym
mieście - to znak odwróconych współrzędnych), czy markery zgadzają się
z trasą, czy warnings i komunikaty fits_time/fits_budget są widoczne,
czy loading/error działają przy wyłączonym backendzie. Spisz listę
rozbieżności względem kontraktu i podaj, po której stronie jest błąd.
```
