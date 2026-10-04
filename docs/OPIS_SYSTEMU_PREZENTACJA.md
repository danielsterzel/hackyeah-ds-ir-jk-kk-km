# VentureFlux — pełny opis systemu i kontekst do prezentacji

## 1. Elevator pitch

VentureFlux to osobisty planer jednodniowego zwiedzania Krakowa. Zamiast zwracać listę popularnych miejsc, zbiera potrzeby użytkownika w krótkim wywiadzie, zamienia je na ustrukturyzowane ograniczenia i buduje wykonalną kolejność atrakcji z uwzględnieniem GPS, dostępnego czasu, budżetu, zainteresowań, godzin otwarcia oraz rzeczywistych czasów przejazdu ulicami.

Najkrótsze uczciwe zdanie techniczne:

> LLM rozumie użytkownika, dane Google Maps opisują miejsca, OpenRouteService opisuje realne przejazdy, a OR-Tools podejmuje decyzję o podzbiorze i kolejności atrakcji.

## 2. Problem

Planowanie dnia w obcym mieście wymaga jednoczesnego ustalenia:

- co interesuje konkretną osobę,
- które miejsca są otwarte,
- ile trwa wizyta,
- ile trwa przejście lub przejazd,
- czy plan mieści się w czasie,
- ile kosztują bilety i transport,
- w jakiej kolejności odwiedzić miejsca.

Zwykła wyszukiwarka odpowiada „co warto zobaczyć”. VentureFlux odpowiada „co możesz zobaczyć dzisiaj, w jakiej kolejności i o której tam dotrzesz”.

## 3. Zakres MVP

System obsługuje:

- Kraków,
- plan jednodniowy,
- rzeczywistą lokalizację startową,
- pieszo, rower i samochód przez OpenRouteService,
- transport publiczny jako uproszczony fallback,
- 21 kategorii,
- godziny otwarcia,
- budżet czasu i pieniędzy,
- preferencje miejsc, jedzenia i tłumów,
- geometrie finalnej trasy,
- research i fallback cen biletów,
- interaktywną mapę i timeline.

MVP świadomie nie obejmuje:

- GTFS i realtime MPK,
- tras multimodalnych,
- realnego wpływu pogody,
- bieżącego zatłoczenia,
- parkingów i rowerów miejskich,
- rezerwacji oraz zakupu biletów,
- trwałego przechowywania planów.

## 4. Architektura

```text
┌──────────────────────────────────────────────────────────────┐
│ Frontend: Next.js 16 + React 19                             │
│ landing / home / planner / Leaflet                          │
└───────────────────────┬──────────────────────────────────────┘
                        │ HTTP JSON
┌───────────────────────▼──────────────────────────────────────┐
│ Backend: FastAPI                                            │
│ questionnaire API + planning API                            │
├──────────────────────────────────────────────────────────────┤
│ LLM extraction       │ dane POI       │ ticket research      │
│ Ollama gpt-oss:120b  │ JSON Apify     │ Ollama web search    │
├──────────────────────┴─────────────────┴──────────────────────┤
│ Preference filter → ORS Matrix → OR-Tools → ORS Directions  │
└──────────────────────────────────────────────────────────────┘
```

### Technologie

Frontend:

- Next.js `16.3.8`,
- React `19.2.8`,
- TypeScript,
- Tailwind CSS 4,
- React Query,
- Leaflet + React Leaflet,
- Lucide.

Backend:

- FastAPI,
- Pydantic v2,
- OR-Tools Routing,
- HTTPX AsyncClient,
- Ollama SDK,
- przygotowane SQLAlchemy/PostgreSQL, niewpięte do aktywnego flow.

Usługi:

- Ollama Cloud — ekstrakcja preferencji i ceny,
- OpenRouteService — macierze i GeoJSON,
- OpenStreetMap — mapa.

## 5. Strony

### `/`

Landing page wyjaśnia wartość produktu, pokazuje trzy kroki i prowadzi do planera.

### `/home`

Ekran wejściowy z CTA i inspiracjami. Karty inspiracji prowadzą do planera, ale nie ustawiają jeszcze automatycznie preferencji.

### `/planner`

1. wybór strategii,
2. budżet,
3. zgoda na GPS,
4. sześć pytań,
5. ekran ładowania,
6. polling wyniku co sekundę,
7. mapa i podsumowanie.

### `/plan`

Przekierowanie kompatybilności do `/planner`.

## 6. API

### `POST /questionnaire/init`

Wejście:

```json
{
  "id": "uuid",
  "latitude": 50.0614,
  "longitude": 19.9372,
  "budgetPln": 100,
  "optimizationStrategy": "cheapest"
}
```

Wyjście:

```json
{
  "question": "Co sprawi, że ten dzień w Krakowie będzie naprawdę Twój? ✨"
}
```

### `POST /questionnaire/answer`

```json
{
  "id": "uuid",
  "answer": "Muzea, historia i architektura"
}
```

Po ostatniej odpowiedzi zwraca HTTP `204` i uruchamia finalizację w tle.

### `GET /planning/{user_id}`

Możliwe statusy:

- `planning`,
- `ready`,
- `failed`.

Frontend odpytuje co sekundę, dopóki trwa planowanie.

### `POST /planning`

Techniczny endpoint przyjmujący bezpośrednio `LLMOutput` i zwracający wewnętrzne plany. Główny frontend używa flow kwestionariusza.

## 7. Sekwencja end-to-end

```text
1. Frontend pobiera GPS.
2. Wysyła UUID, GPS, budżet i strategię.
3. Backend tworzy sesję wywiadu w pamięci.
4. Zwraca kolejno 6 pytań.
5. Odpowiedzi trafiają do historii.
6. Po ostatniej odpowiedzi zwracane jest 204.
7. LLM tworzy walidowany LLMOutput.
8. Backend rozwija kategorie i przywraca budżet z UI.
9. Dataset 877 miejsc jest mapowany do taksonomii.
10. Miejsca są filtrowane według promienia, wykluczeń i godzin.
11. Kandydaci są oceniani według ratingu, popularności i preferencji.
12. Wybierane jest maksymalnie 30 atrakcji.
13. GPS jest dodawany jako węzeł 0.
14. ORS Matrix zwraca realny czas i dystans każdej pary.
15. Encoder buduje graf.
16. OR-Tools wybiera podzbiór i kolejność.
17. Decoder buduje timeline.
18. ORS Directions pobiera GeoJSON finalnych odcinków.
19. Timeline aktualizuje się finalnymi czasami.
20. TicketService dodaje ceny.
21. Mapper buduje RoutePlan.
22. Frontend rysuje mapę, listę i summary.
```

## 8. Moduły backendu

### `api/questionnaire.py`

- utrzymuje sesje wywiadu,
- uruchamia finalizację w tle,
- zapisuje status planowania i błąd.

### `service/llm/questionnaire.py`

- ładuje pytania i prompt,
- buduje kontekst,
- odpytuje Ollama,
- normalizuje aliasy,
- waliduje JSON,
- wykonuje retry,
- tworzy fallback.

### `planning_json_poi_service.py`

- wczytuje dataset,
- mapuje rekordy do `POI`,
- normalizuje godziny,
- mapuje kategorie,
- pomija rekordy zamknięte, reklamowe, błędne i zduplikowane.

### `planning_poi_filter_service.py`

- stosuje promień 25 km,
- respektuje wykluczenia,
- sprawdza godziny,
- podbija preferencje,
- stosuje proxy tłumów,
- buduje shortlistę.

### `planning_ors_routing_service.py`

- mapuje tryby na profile ORS,
- pobiera macierz metrów i sekund,
- pobiera finalne GeoJSON,
- ma timeout i walidację odpowiedzi.

### `planning_simple_connection_service.py`

Fallback: linia prosta × 1.3, stała prędkość i koszt/km.

### `planning_simple_solver_encoder.py`

Zamienia POI i połączenia na węzły/krawędzie solvera oraz koduje reward, koszty i okna.

### `planning_or_solver.py`

Buduje OR-Tools Routing z wymiarami Time i Money, opcjonalnymi węzłami i limitem 5 sekund.

### `planning_simple_solver_decoder.py`

Odtwarza POI, przejazdy, oczekiwanie na otwarcie, arrival/departure i sumy.

### `ticket_price/ticket_price.py`

Wyszukuje cenniki, wyciąga ceny przez LLM, cache'uje wynik i ma statyczny fallback.

### `planning_mapper.py`

Tworzy kontrakt frontendu, summary i warningi.

## 9. Modele

### `LLMOutput`

Semantyczny opis intencji użytkownika. Jest celowo oddzielony od domeny.

### `PlanningRequest`

Znormalizowane daty, `lat/lng`, enum transportu i preferencje gotowe do logiki.

### `POI`

Miejsce z lokalizacją, typami, ratingiem, opiniami, godzinami, reward i kosztem wizyty.

### `POIConnection`

Skierowany odcinek: mode, dystans, czas, koszt, geometria i flaga fallbacku.

### `SolverInput`

Graf wejściowy: węzły, krawędzie, start, budżety i wagi.

### `Plan`

Wewnętrzny wynik solvera z timeline'em.

### `RoutePlan`

Stabilny kontrakt UI: summary, stops, legs, geometrie i warnings.

## 10. Routing

### Macierz

ORS dostaje GPS i kandydatów jako `[lon, lat]`. Macierz jest skierowana, więc `A → B` może różnić się od `B → A`.

Realne `distance_m` i `duration_s` są kodowane w krawędziach OR-Tools. Routing nie jest tylko dekoracją mapy.

### Directions

GeoJSON jest pobierany po optymalizacji tylko dla kilku finalnych odcinków, a nie dla setek par.

### Profile

| Użytkownik | ORS |
|---|---|
| pieszo | `foot-walking` |
| rower | `cycling-regular` |
| auto | `driving-car` |
| komunikacja | fallback bez ORS transit |

## 11. Dlaczego OR-Tools

Trzeba zdecydować jednocześnie:

- które atrakcje pominąć,
- które zachować,
- w jakiej kolejności je odwiedzić,
- czy mieszczą się w godzinach,
- czy mieszczą się w czasie,
- czy mieszczą się w budżecie znanym przed ticket researchem.

To wariant orienteering/prize-collecting routing. Reward atrakcji staje się karą za jej pominięcie. Solver może pominąć jedno miejsce, jeśli blokowałoby kilka lepszych.

## 12. Frontend wyniku

Mapa:

- OpenStreetMap,
- Leaflet po stronie klienta,
- `GeoJSON` dla ORS,
- `Polyline` dla fallbacku,
- automatyczny fit bounds,
- kliknięcie przystanku centruje mapę.

Kolory:

- zielona przerywana — pieszo,
- pomarańczowa — rower,
- niebieska — komunikacja,
- czerwona — samochód/taxi.

Lista pokazuje:

- GPS jako start,
- czas startu/przyjazdu,
- cenę lub „cena nieznana”,
- zamknięcie,
- warning,
- między stopami czas i transport.

Summary pokazuje:

- koszt,
- budżet,
- zieloną strzałkę i zapas albo czerwoną i przekroczenie,
- całkowity czas,
- czas samych dojazdów,
- dystans,
- dystans pieszy,
- liczbę atrakcji.

## 13. Odporność

### LLM

- schemat Pydantic,
- druga próba,
- fallback 09:00–18:00 przy niepoprawnym JSON.

### ORS

- AsyncClient,
- timeout 12 sekund,
- `raise_for_status`,
- pełny graf fallbackowy,
- częściowe zastępowanie tylko poprawnych par,
- brak crasha przy timeoutach.

### Bilety

- cache po nazwie,
- obsługa limitu 429,
- mocki znanych atrakcji,
- brak wymyślonej ceny dla nieznanych.

### Dataset

- pojedynczy uszkodzony rekord nie zatrzymuje importu,
- nieznane godziny nie usuwają miejsca,
- niepewność jest widoczna jako warning.

## 14. Warningi

| Kod | Znaczenie |
|---|---|
| `ROUTING_FALLBACK` | brak realnej geometrii; możliwa linia prosta |
| `TIME_EXCEEDED` | końcowy plan przekracza czas |
| `OPENING_HOURS_UNKNOWN` | brak godzin |
| `OPENING_WINDOW_UNKNOWN` | nie dopasowano okna do wizyty |
| `CLOSES_SOON` | zamknięcie do 45 minut po wyjściu |

Budżet jest raportowany bezpośrednio w summary i kafelku.

## 15. Stan i persystencja

W pamięci procesu znajdują się:

- sesje kwestionariusza,
- statusy,
- LLMOutput,
- plany,
- błędy.

Konsekwencje:

- restart usuwa sesje,
- wiele instancji bez wspólnego storage jest ryzykowne,
- to rozwiązanie hackathonowe, nie produkcyjne.

Repo ma modele SQLAlchemy dla `Place`, `Trip`, `TripPlan`, `PlanStop` i `RouteLeg`, ale aktywny pipeline ich nie używa.

## 16. ENV

Backend:

```env
DATABASE_URL=...
DATABASE_PASSWORD=...
OLLAMA_API_KEY=...
ORS_API_KEY=...
```

Frontend:

```env
NEXT_PUBLIC_BACKEND_URL=https://backend.example
```

Bez `ORS_API_KEY` planner działa na fallbacku. Klucz Ollama jest wymagany przez settings. Fallback kwestionariusza chroni przed złym JSON-em; błąd samego requestu do Ollama nadal kończy finalizację błędem. TicketService obsługuje błędy per atrakcja własnym fallbackiem.

### CORS i deployment

Backend dopuszcza requesty z:

- `http://localhost:3000`,
- `http://127.0.0.1:3000`,
- deploymentów Vercel zgodnych z `https://hackyeah-ds-ir-jk-kk-*.vercel.app`.

Frontend usuwa końcowy `/` z `NEXT_PUBLIC_BACKEND_URL`. Przy deploymentcie trzeba upewnić się, że adres backendu jest dostępny przez HTTPS i pasuje do konfiguracji CORS.

## 17. Testy

Backend ma 71 przechodzących testów. Zakres:

- mapping kategorii,
- `park` bez fałszywego `parking`,
- preferowane kategorie w shortlist,
- warianty LLMOutput,
- pierwszy tryb rowerowy,
- ograniczenia OR-Tools,
- `most_places`,
- okna czasowe,
- timeline,
- fallback ORS,
- `[lon, lat]`,
- realne czasy ORS w solverze,
- GPS → pierwsza atrakcja,
- mockowane ceny i suma.

Frontend przechodzi ESLint oraz produkcyjny build Next.js.

## 18. Co jest realne, a co przybliżone

### Realne

- GPS jako start,
- macierz ulic dla walking/bicycle/car,
- czasy ORS używane przez OR-Tools,
- GeoJSON finalnych odcinków,
- dojazd do pierwszej atrakcji,
- timeline z przejazdami i wizytami,
- okna otwarcia,
- preferowanie i wykluczanie kategorii,
- `most_places`,
- finalna estymacja kosztu i wykrycie przekroczenia.

### Przybliżone

- tłumy = liczba recenzji,
- transit = dystans × 1.3 / 20 km/h,
- auto = 0.50 zł/km bez parkingu,
- każda wizyta = 60 minut,
- jedzenie = dopasowanie markerów lokalu i aliasów kuchni w datasecie,
- brakująca geometria = prosta.

### Zbierane, ale niewykorzystane

- pogoda,
- transporty po pierwszym,
- end location jako obowiązkowy koniec.

## 19. Ryzyka przed demo

1. Użyć sprawdzonego promptu.
2. Wybrać pieszo/rower/auto, żeby pokazać ORS.
3. Transit nazwać fallbackiem i roadmapą GTFS.
4. Niski budżet może zostać przekroczony po biletach.
5. „Bez tłumów” wzmocnić odpowiedzią tekstową.
6. Kuchnia włoska ma mapping polsko-angielski, ale nadal zależy od kategorii dostępnych w datasecie.
7. Brak GeoJSON nie oznacza braku planu.

## 20. Scenariusz demo

Ustawienia:

- „Najwięcej miejsc”,
- budżet 150–250 zł,
- rower lub pieszo,
- lokalizacja w Krakowie.

Odpowiedzi:

```text
Interesują mnie muzea, historia i architektura.
Najchętniej rowerem, pieszo też może być.
Jedzenie nie jest dla mnie ważne.
Jutro od 10:00, mam około 7 godzin.
Tłumy nie są problemem.
Pogoda nie zmienia planu.
```

Pokazać:

1. brak ręcznego wybierania atrakcji,
2. rzeczywisty GPS jako start,
3. dojazd przed pierwszą atrakcją,
4. trasy po drogach,
5. czas i transport między stopami,
6. całkowity czas kontra czas dojazdów,
7. zapas lub przekroczenie budżetu.

## 21. Narracja do prezentacji

### Problem

> Plan jednego dnia to połączenie zainteresowań, mapy, godzin, cen i dojazdów. To problem optymalizacyjny, nie zwykłe wyszukiwanie.

### Rozwiązanie

> LLM nie układa trasy. Rozumie język użytkownika i zamienia go na ścisły JSON. Deterministyczny pipeline filtruje dane, pobiera realne czasy i przekazuje problem do OR-Tools.

### Technologia

> OpenRouteService buduje macierz czasu pomiędzy GPS-em i kandydatami. OR-Tools wybiera miejsca oraz kolejność przy ograniczeniach. Geometrię pobieramy dopiero dla finalnych odcinków.

### Wartość

> Wynikiem nie jest lista, tylko timeline: kiedy wyjść, ile trwa pierwszy dojazd, kiedy kończy się wizyta i ile trwa kolejny odcinek.

### Roadmapa

> Następne kroki to GTFS, ceny przed solverem, aktualne tłumy, pogoda i multimodalność.

## 22. Czego nie mówić

Nie mówić:

- „Obsługujemy prawdziwe autobusy i tramwaje”.
- „System zna aktualne tłumy”.
- „Pogoda przenosi plan do wnętrz”.
- „Każdy plan zawsze mieści się w budżecie po aktualnych cenach”.
- „Mieszamy rower, spacer i auto w jednej trasie”.

Mówić:

- „Pieszo, rower i auto mają prawdziwy routing; transit jest fallbackiem pod GTFS”.
- „Tłumy modelujemy przez proxy popularności”.
- „Preferencja pogodowa jest już w kontrakcie, integracja prognozy to kolejny moduł”.
- „Po researchu cen jasno pokazujemy przekroczenie”.
- „W MVP cały plan używa podstawowego transportu”.

## 23. Liczby do slajdu

Pewne liczby z kodu i danych:

- 877 miejsc,
- 21 kategorii,
- 517 miejsc z godzinami,
- 808 miejsc z ratingiem,
- 30 kandydatów + GPS,
- 3 realne profile ORS,
- 6 pytań,
- 5 sekund limitu solvera,
- 12 sekund timeoutu ORS,
- 71 testów backendowych.

Nie podawać bez pomiaru:

- średniego czasu generowania,
- procentowej poprawy trasy,
- procentu planów w budżecie,
- liczby użytkowników.

## 24. Metryki do nagrania

Na 3–5 identycznych scenariuszach warto zmierzyć:

1. czas od ostatniej odpowiedzi do `ready`,
2. czas samego OR-Tools,
3. liczbę kandydatów,
4. liczbę atrakcji,
5. czas i dystans dojazdów,
6. liczbę legów GeoJSON vs fallback,
7. sumę reward,
8. różnicę względem losowej kolejności tych samych miejsc.

Najlepsza metryka prezentacyjna:

```text
czas przejazdów planu OR-Tools
vs
czas przejazdów tych samych atrakcji w losowej kolejności
```

Musi zostać policzona na tej samej macierzy ORS.

## 25. Roadmapa

### Mała zmiana, duży efekt

1. Cache/pobranie cen przed solverem.
2. Twarde `avoidCrowds` przy strategii „Bez tłumów”.
3. Osobne wagi celu dla `cheapest` i `fastest`.
4. Kilka wariantów candidate limits/wag dla prawdziwych alternatyw.
5. Różne czasy wizyt według kategorii.

### Kolejny etap

1. GTFS static i realtime.
2. Multimodalność.
3. Parkingi.
4. Stacje roweru miejskiego.
5. Prognoza i indoor/outdoor.
6. Tłumy zależne od godziny.
7. PostgreSQL i kolejka zadań.
8. Cache macierzy i cen.

## 26. Podsumowanie

Najważniejszy jest podział odpowiedzialności:

- LLM rozumie odpowiedzi,
- Pydantic pilnuje kontraktu,
- filtr ogranicza przestrzeń,
- ORS dostarcza realne przejazdy,
- OR-Tools podejmuje decyzję,
- mapper stabilizuje API,
- Leaflet pokazuje wynik człowiekowi.

Dzięki temu GTFS może zastąpić transit fallback, ceny mogą trafić przed solver, a pogoda może dodać nowy mnożnik reward bez przepisywania całego systemu.
