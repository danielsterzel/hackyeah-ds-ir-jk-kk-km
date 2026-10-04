# Proces decyzyjny planera VentureFlux

Dokument opisuje faktyczne zachowanie aktualnego kodu. Rozdziela elementy działające realnie od pól, które są już zbierane, ale nie mają jeszcze pełnego wpływu na wynik.

## 1. Przepływ w jednym zdaniu

Odpowiedzi użytkownika są zamieniane przez LLM na walidowany JSON, JSON jest mapowany na model domenowy, lokalny zbiór miejsc jest filtrowany i oceniany, OpenRouteService wylicza macierz rzeczywistych czasów i dystansów, OR-Tools wybiera kolejność oraz podzbiór atrakcji, a na końcu system pobiera geometrie tylko dla wybranych odcinków i uzupełnia ceny biletów.

```text
frontend
  └─ GPS + budżet + strategia + 6 odpowiedzi
       └─ Ollama / gpt-oss:120b
            └─ LLMOutput (walidowany JSON)
                 └─ PlanningRequest
                      ├─ 877 rekordów z lokalnego datasetu Google Maps/Apify
                      ├─ filtrowanie + ranking + shortlist do 30 atrakcji
                      ├─ użytkownik jako pierwszy, osobny węzeł
                      ├─ ORS Matrix: realne distance/duration
                      └─ OR-Tools: podzbiór + kolejność + okna czasowe
                           └─ ORS Directions tylko dla finalnych odcinków
                                └─ ceny biletów
                                     └─ RoutePlan dla Leafleta
```

## 2. Wywiad z użytkownikiem

### 2.1. Dane zbierane przed pytaniami

Frontend wysyła do `POST /questionnaire/init`:

```json
{
  "id": "UUID użytkownika",
  "latitude": 50.0614,
  "longitude": 19.9372,
  "budgetPln": 100,
  "optimizationStrategy": "most_places"
}
```

- `id` jest generowane przez `crypto.randomUUID()` i przechowywane w `localStorage`.
- GPS pochodzi z `navigator.geolocation.getCurrentPosition`.
- Geolokalizacja używa `enableHighAccuracy: true`, timeoutu 10 sekund i cache maksymalnie 60 sekund.
- Budżet w interfejsie ma zakres `0–500 zł` ze skokiem `10 zł`; backendowy schemat dopuszcza `0–2000 zł`.
- Strategia jest wybierana jawnie przed wywiadem.

### 2.2. Pytania

Pytania są stałe i zadawane w kolejności:

1. Co sprawi, że ten dzień w Krakowie będzie naprawdę Twój?
2. Jak chcesz odkrywać miasto — pieszo, rowerem czy inaczej?
3. Robimy przystanek na coś pysznego? Jeśli tak, na co masz ochotę?
4. Kiedy ruszamy i ile czasu mamy?
5. Wolisz miejski puls czy miejsca bez tłumów?
6. Deszcz zmienia plan, czy przygoda trwa dalej?

Pytania nie są generowane dynamicznie przez LLM. Backend czyta je z `questions.txt`. LLM pracuje dopiero po zebraniu całej rozmowy.

### 2.3. Kontekst przekazywany do LLM

Do historii rozmowy trafia:

- aktualna data i czas,
- strefa `Europe/Warsaw`,
- rzeczywiste współrzędne użytkownika,
- strategia wybrana w UI,
- zamknięta lista dozwolonych kategorii.

Model to `gpt-oss:120b` przez Ollama Cloud. Wywołanie używa `temperature = 0`, `think = false`, schematu JSON wygenerowanego z Pydantic `LLMOutput` i `keep_alive = 1m`.

### 2.4. Reguły ekstrakcji

Prompt wymaga między innymi:

- uwzględnienia całej rozmowy,
- zastosowania późniejszych korekt zamiast wcześniejszych deklaracji,
- usunięcia jawnie odrzuconych preferencji,
- zachowania wszystkich zaakceptowanych alternatyw,
- rozdzielenia atrakcji od preferencji kulinarnych,
- niewymyślania końcowej lokalizacji,
- ustawienia pustych list i `false`, jeśli użytkownik nie podał preferencji,
- uporządkowania transportów od preferowanego do akceptowalnych fallbacków,
- użycia GPS i strategii z kontekstu aplikacji.

Jeśli odpowiedź modelu nie przejdzie walidacji, system dodaje instrukcję o zwróceniu wszystkich pól i wykonuje drugą próbę. Po dwóch niepoprawnych odpowiedziach używa fallbacku:

- jutro `09:00–18:00`,
- GPS użytkownika,
- budżet z UI,
- strategia z UI,
- transport pieszy,
- puste preferencje,
- brak unikania tłumów i brak wrażliwości pogodowej.

## 3. JSON zwracany przez LLM

Przykładowy wynik:

```json
{
  "budgetPln": 150,
  "startAt": "2026-10-05T09:00:00+02:00",
  "endAt": "2026-10-05T17:00:00+02:00",
  "startLocation": {
    "latitude": 50.0614,
    "longitude": 19.9372
  },
  "endLocation": null,
  "preferredCategories": ["museum", "historic"],
  "foodPreferences": ["italian"],
  "transportModes": ["bicycle", "walking"],
  "avoidCrowds": true,
  "weatherSensitive": true,
  "optimizationStrategy": "most_places",
  "excludedCategories": ["nightlife"]
}
```

Pydantic akceptuje nazwy camelCase i snake_case, ponieważ schemat LLM ma generator aliasów `to_camel`.

### 3.1. Pola i ich realny wpływ

| Pole | Realny wpływ obecnie | Siła |
|---|---|---|
| `budgetPln` | limit pieniędzy w OR-Tools, potem porównanie finalnego kosztu | silny, ale bilety są dodawane później |
| `startAt` | początek osi czasu, data okien otwarcia | bardzo silny |
| `endAt` | twardy budżet czasu `endAt - startAt` | bardzo silny |
| `startLocation` | pierwszy węzeł macierzy i trasy | bardzo silny |
| `endLocation` | tylko ranking odległości kandydatów; nie tworzy końcowego węzła | słaby / niepełny |
| `preferredCategories` | priorytet shortlisty i mnożnik nagrody | silny |
| `foodPreferences` | dopasowanie tekstowe nazwy/typów i mnożnik nagrody | średni, zależny od danych |
| `transportModes` | używany jest tylko pierwszy tryb | bardzo silny dla pierwszego elementu |
| `avoidCrowds` | obniża reward popularnych miejsc według liczby recenzji | umiarkowany, tylko proxy |
| `weatherSensitive` | zapisane, ale bez dalszego użycia | brak wpływu |
| `optimizationStrategy` | `most_places` realnie zmienia reward; inne strategie mają ograniczony wpływ | zróżnicowany |
| `excludedCategories` | twarde usunięcie kandydatów z tagiem | bardzo silny |

### 3.2. Co jest nadpisywane po LLM

- Budżet jest zawsze twardo nadpisywany wartością z formularza. LLM nie może zmienić kwoty ustawionej suwakiem.
- Kategorie są rozwijane kodowo po walidacji.
- GPS i strategia są przekazywane w kontekście i wymagane promptem, ale po poprawnej walidacji nie są ponownie nadpisywane kodowo. Fallback używa ich bezpośrednio.

## 4. Mapping kategorii

### 4.1. Dozwolona taksonomia

```text
historic, castle, museum, park, nature, architecture, art,
entertainment, music, concert, theater, cinema, sport, forest,
landmark, religious, viewpoint, monument, garden, nightlife, shopping
```

LLM nie może zwrócić kategorii spoza tej listy.

### 4.2. Rozszerzanie preferencji po LLM

| Preferencja | Automatycznie dodawane |
|---|---|
| `castle` | `historic`, `architecture` |
| `concert` | `music` |
| `forest` | `nature` |
| `garden` | `nature` |
| `monument` | `historic` |
| `religious` | `historic`, `architecture` |

Po rozszerzeniu usuwane są kategorie z `excludedCategories`.

Przykład: `preferred=[castle]`, `excluded=[architecture]` daje finalnie `[castle, historic]`.

### 4.3. Mapping danych Apify/Google Maps

| Kategoria źródłowa | Tagi wewnętrzne |
|---|---|
| atrakcja turystyczna | landmark |
| obiekt/miejsce historyczne | historic, landmark |
| muzeum historycznego miejsca | museum, historic, landmark |
| budynek zabytkowy | historic, architecture, landmark |
| zamek | castle, historic, architecture, landmark |
| willa | architecture |
| galeria sztuki | art |
| muzeum sztuki / nowoczesnej / rzeźby | museum, art |
| promocja sztuki / sztuka / malarstwo / rzeźbiarz | art |
| rezerwat przyrody / teren spacerowy | nature |
| park / park miejski / krajobrazowy | park, nature |
| park pamięci | park, nature, monument |
| ogród / osiedlowy / botaniczny | garden, nature |
| las państwowy | forest, nature |
| zoo | nature, entertainment |
| centrum rozrywki / rozrywka / park rozrywki / sala lub plac zabaw | entertainment |
| tor gokartowy | entertainment, sport |
| klub komediowy | entertainment, nightlife |
| sala koncertowa / filharmonia | music, concert |
| opera | music, concert, theater |
| klub muzyczny / bar z muzyką na żywo | music, nightlife |
| amfiteatr | music, concert, theater |
| centrum/dom kultury | art, entertainment |
| kino | cinema, entertainment |
| centra sportowe / klub sportowy / siłownia / skatepark | sport |
| punkt lub taras widokowy | viewpoint, landmark |
| pomnik | monument, landmark |
| rzeźba / posąg | monument, art |
| przestrzeń pamięci | monument, historic |
| bar / pub / gastropub / piwiarnia / winiarnia / klub | nightlife |
| supermarket | shopping |

Dodatkowe reguły wzorcowe:

- każda kategoria zawierająca `muzeum` dostaje `museum`,
- kategorie zaczynające się od `teatr` oraz `grupa teatralna` dostają `theater`,
- kościół, klasztor, kaplica, świątynia, parafia, bazylika, katedra, sanktuarium i synagoga dostają `religious`,
- kategorie zaczynające się od `sklep` dostają `shopping`.

Porównania preferencji i wykluczeń są wykonywane po dokładnych tagach, nie jako luźne podciągi. `park` nie dopasowuje więc `parking`.

## 5. Mapping transportu

### 5.1. Normalizacja tekstu LLM

| Wartość wejściowa | Po normalizacji |
|---|---|
| `walk`, `on foot` | `walking` |
| `bike`, `cycling`, `by bike`, `rower`, `rowerem` | `bicycle` |
| `public transit`, `transit` | `public_transport` |

### 5.2. LLM → domena → ORS → frontend

| LLM | `TravelMode` | Profil ORS | UI |
|---|---|---|---|
| `walking`, `walk` | `WALK` | `foot-walking` | `walk` / Pieszo |
| `bicycle`, `cycling` | `BICYCLE` | `cycling-regular` | `bike` / Rower |
| `car`, `drive`, `driving` | `DRIVE` | `driving-car` | `car` / Samochód |
| `taxi` | `DRIVE` | `driving-car` | `car` / Samochód |
| `scooter` | `BICYCLE` | `cycling-regular` | `bike` / Rower |
| `public_transport`, `tram`, `transit` | `TRANSIT` | brak | `bus` / Komunikacja |

System wybiera wyłącznie pierwszy element `transportModes`. `[bicycle, walking]` oznacza plan w całości rowerowy. Nie ma odcinków mieszanych.

## 6. Źródło i przygotowanie miejsc

System czyta lokalny eksport Google Maps/Apify:

`backend/resources/dataset_crawler-google-places_2026-10-03_15-34-29-547.json`

Aktualny zbiór zawiera:

- 877 rekordów i unikalnych identyfikatorów,
- 517 miejsc z godzinami otwarcia,
- 808 miejsc z oceną.

Rekord odpada, jeśli nie ma `placeId` lub współrzędnych, jest zamknięty, jest reklamą albo dubluje identyfikator.

Godziny są normalizowane z polskich i angielskich nazw dni, formatów 12/24-godzinnych, przedziałów przez północ i oznaczeń całodobowych.

Domyślnie:

- wizyta trwa 60 minut,
- cena wizyty przed późniejszym researchem wynosi 0 zł,
- reward jest liczony z ratingu i liczby opinii.

## 7. Filtrowanie i shortlista

### 7.1. Promień i filtry twarde

Wybierane są miejsca do 25 km od GPS. POI jest usuwane, jeśli:

- leży poza promieniem,
- ma tag z `excludedCategories`,
- znane godziny nie pozwalają zmieścić 60-minutowej wizyty.

Brak godzin nie usuwa miejsca; później generuje warning.

Jeśli istnieje `endLocation`, ranking używa sumy odległości `start → POI + end → POI`, ale trasa nie kończy się jeszcze obowiązkowo w tym punkcie.

### 7.2. Reward bazowy

```text
reward = rating × (1 + log10(1 + liczba_recenzji))
```

Brak ratingu oznacza `3.0`, brak recenzji `0`.

### 7.3. Preferencje

```text
dokładny tag w preferredCategories: reward × 1.5
dopasowana foodPreference w nazwie lub typach: reward × 1.25
```

Kandydaci pasujący do kategorii lub jedzenia trafiają do pierwszego koszyka shortlisty. Dopiero potem rozpatrywane są inne miejsca. Ogólne odpowiedzi takie jak `restauracje`, `restaurant`, `jedzenie` i `coś zjeść` rozpoznają kategorie lokali gastronomicznych. Popularne nazwy kuchni, m.in. polska, włoska, grecka, japońska, chińska, indyjska i meksykańska, mają mapping polsko-angielski.

### 7.4. Tłumy

Przy `avoidCrowds = true`:

```text
reward = reward / (1 + log10(1 + liczba_recenzji) / 10)
```

To proxy popularności, nie bieżące dane o tłumie.

### 7.5. Ranking

```text
score = odległość × distance_weight / reward
```

`distance_weight` to `2.0` dla podstawowego trybu pieszego, inaczej `1.0`. Ponieważ jest wspólnym mnożnikiem wszystkich kandydatów, obecnie sam nie zmienia względnej kolejności. Realny wpływ chodzenia pojawia się w czasach ORS.

Do routingu trafia maksymalnie 30 atrakcji plus start, czyli maksymalnie 31 lokalizacji.

## 8. Wpływ strategii

### `most_places`

Każda atrakcja dostaje:

```text
1000 punktów bazowo
+10 za preferredCategories
+5 za foodPreferences
```

Solver przede wszystkim maksymalizuje liczbę wykonalnych atrakcji. Preferencje rozstrzygają remisy.

### `cheapest`

Wybór planu sortuje po najmniejszym koszcie, potem większej liczbie atrakcji i krótszym czasie. Jednak `candidate_limits = (30,)` zwykle generuje tylko jeden plan, więc końcowe porównanie wariantów ma ograniczony wpływ. Budżet pozostaje twardym constraintem przed dodaniem finalnych biletów.

### `fastest`

Wybiera najmniejszy łączny czas, potem większą liczbę atrakcji. Przy jednym wariancie wpływ końcowego wyboru jest ograniczony. Wszystkie strategie mają tie-breaker czasu wewnątrz OR-Tools.

### `least_crowded`

Wybiera największy reward. Faktyczna kara popularności działa tylko, gdy JSON ma `avoidCrowds = true`. Sam kafelek „Bez tłumów” nie nadpisuje tej flagi kodowo.

## 9. Routing przed optimizerem

### 9.1. Start

System tworzy specjalny POI:

```text
id = __user_start__
name = Twoja lokalizacja
location = startLocation
visit time = 0
reward = 0
```

Jest pierwszym elementem macierzy i obowiązkowym startem trasy. Nie ma stałego nadpisania GPS współrzędnymi Krakowa.

### 9.2. ORS Matrix

Dla pieszo, roweru i auta:

```http
POST https://api.heigit.org/openrouteservice/v2/matrix/{profile}
Authorization: ORS_API_KEY
```

```json
{
  "locations": [[19.9372, 50.0614], [19.9352, 50.0540]],
  "metrics": ["distance", "duration"],
  "units": "m"
}
```

ORS używa `[longitude, latitude]`. Zwrócone skierowane metry i sekundy zastępują fallback przed OR-Tools. Timeout wynosi 12 sekund, a klient używa `raise_for_status()`.

### 9.3. Fallback

Fallback istnieje zawsze. Jest używany przy braku klucza, transit, błędzie całego requestu lub brakującej parze:

```text
distance = lokalna odległość prosta × 1.3
duration = distance / średnia prędkość
```

| Tryb | Prędkość | Koszt/km |
|---|---:|---:|
| pieszo | 4.5 km/h | 0 zł |
| rower | 15 km/h | 0 zł |
| transit | 20 km/h | 0.30 zł |
| auto | 40 km/h | 0.50 zł |

Transit nie zna rozkładów, przesiadek, przystanków ani rzeczywistej ceny biletu.

## 10. Kodowanie dla OR-Tools

Każdy kandydat staje się `SolverNode` z reward, kosztem wizyty i oknami czasowymi. Każde połączenie staje się skierowaną krawędzią:

```text
edge.time_s = ORS duration lub fallback
edge.money_minor = koszt przejazdu × 100
```

Budżety:

```text
time budget = endAt - startAt
money budget = budgetPln × 100
```

To realne wartości ORS trafiają do optimizera; geometria nie jest mu potrzebna.

## 11. Model OR-Tools

To wariant orienteering/prize-collecting routing:

- atrakcje są opcjonalne,
- pominięcie ma karę równą reward,
- czas i pieniądze są ograniczeniami,
- okna otwarcia ograniczają godzinę wizyty,
- startem jest GPS,
- trasa kończy się przy ostatniej atrakcji i nie wraca automatycznie.

Dla przejścia `i → j`:

```text
time(i,j) = visit_time(i) + travel_time(i,j)
money(i,j) = visit_price(i) + travel_cost(i,j)
```

Wizyta w ostatnim POI jest doliczana na łuku do sztucznego końca.

Model domenowy wspiera wagi czasu i pieniędzy, ale obecnie obie wynoszą zero. Koszt łuków zawiera tie-breaker:

```text
arc_cost += czas_w_sekundach // 10
```

Pominięcie węzła kosztuje `round(reward × 1000)`. W praktyce solver zachowuje wartościowe miejsca, respektuje limity i przy podobnym reward preferuje krótszą trasę.

Godziny otwarcia są sekundami od startu. Najpóźniejszy start wizyty to `zamknięcie - czas wizyty`. Solver może czekać na otwarcie.

Wyszukiwanie:

- `PATH_CHEAPEST_ARC`,
- `GUIDED_LOCAL_SEARCH`,
- limit 5 sekund,
- wynik często `feasible`, gdy nie udowodniono optimum.

## 12. Timeline

Decoder symuluje najwcześniejszy harmonogram:

```text
t = 0 na startAt
dodaj realny czas przejazdu
jeśli za wcześnie: poczekaj na otwarcie
arrival = t
dodaj czas wizyty
departure = t
```

Przykład:

```text
10:00  Twoja lokalizacja
        13 min ORS
10:13  Wawel — przyjazd
11:13  Wawel — wyjazd
         8 min ORS
11:21  Rynek — przyjazd
```

Pierwszy odcinek `startLocation → pierwsza atrakcja` jest częścią macierzy, ograniczeń, całkowitego czasu, listy odcinków i timeline'u.

## 13. Geometrie po optimizerze

Po wyborze kolejności backend wywołuje dla każdego finalnego odcinka:

```http
POST /v2/directions/{profile}/geojson
```

Zapisuje GeoJSON `LineString`, finalny dystans i czas. Geometria jest pobierana tylko dla finalnych odcinków, nie wszystkich par.

Jeśli Directions zawiedzie, pozostaje czas/dystans z macierzy, ale bez geometrii. Leaflet rysuje linię prostą i pojawia się `ROUTING_FALLBACK`.

## 14. Ceny biletów i budżet

Dla finalnych atrakcji `TicketService`:

1. wyszukuje do 5 wyników przez Ollama Web Search,
2. pobiera strony,
3. przekazuje materiał do `gpt-oss:120b`,
4. waliduje `TicketInfo`,
5. przyjmuje `maxPrice`, a w braku `minPrice`,
6. przy błędzie lub 429 korzysta ze statycznych mocków,
7. nie wymyśla ceny nieznanego miejsca.

### Najważniejsze ograniczenie

Ceny biletów są pobierane **po wyborze trasy przez OR-Tools**.

- OR-Tools używa ceny POI znanej przed optymalizacją.
- Dataset domyślnie ma 0 zł.
- Koszt transportu jest uwzględniany wcześniej.
- Bilety są dopisywane do końcowego podsumowania.
- Plan może po tym przekroczyć budżet; UI pokazuje ostrzeżenie.

Nie należy mówić, że solver zawsze dobiera atrakcje według finalnych cen biletów.

## 15. Odpowiedź dla frontendu

Każdy `RouteLeg` zawiera:

```text
mode
distance_m
duration_min
cost_pln
coords jako fallback [lat, lng]
geometry GeoJSON [lon, lat], jeśli ORS zadziałał
```

Summary zawiera koszt, czas dnia, dystans, dystans pieszy, liczbę atrakcji, zgodność z czasem/budżetem i przekroczenia. Frontend osobno sumuje `duration_min` legów jako „Czas dojazdów”.

## 16. Macierz zależności

| Wejście | Shortlista | Reward | ORS | Constraints | UI |
|---|---:|---:|---:|---:|---:|
| GPS | tak | nie | pierwszy punkt | start | marker startu |
| start/end czasu | godziny | nie | nie | twardy limit | timeline |
| budżet | nie | nie | nie | twardy przed biletami | zapas/przekroczenie |
| kategorie | priorytet | ×1.5 | nie | przez reward | wybrane miejsca |
| wykluczenia | twardy filtr | — | — | — | brak tych miejsc |
| jedzenie | priorytet przy matchu | ×1.25 | nie | przez reward | możliwy lokal |
| pierwszy transport | pośrednio | nie | wybiera profil | czasy i koszty | tryb legów |
| kolejne transporty | nie | nie | nie | nie | nie |
| avoidCrowds | nie | kara popularności | nie | przez reward | pośrednio |
| weatherSensitive | nie | nie | nie | nie | nie |
| most_places | nie | 1000 + bonusy | nie | mocno | więcej miejsc |

## 17. Ograniczenia

1. Brak prawdziwego transit/GTFS.
2. Brak tras mieszanych.
3. Brak parkingów i rowerów miejskich.
4. Pogoda nie wpływa na plan.
5. Tłumy to proxy liczby opinii.
6. Ceny biletów trafiają po optimizerze.
7. Jedzenie działa na markerach i aliasach tekstowych lokalnego datasetu; nie korzysta z zewnętrznej bazy restauracji.
8. `endLocation` nie jest końcem trasy.
9. Wizyty mają domyślnie 60 minut.
10. Stan jest przechowywany w pamięci procesu.

## 18. Elementy obecne w kodzie, ale nieaktywne w głównym flow

- `_budget_for_strategy()` definiuje kwoty dla strategii, ale nigdzie nie jest wywoływane. Budżet pochodzi z suwaka użytkownika.
- `_MAX_TICKET_LOOKUPS_PER_PLAN = 12` jest zdefiniowane, ale pętla cen nie stosuje obecnie tego limitu.
- `SimplePlanningMapper` tworzy starszy `PlotterPayload`; aktywny frontend korzysta z `RoutePlanMapper`.
- Modele SQLAlchemy/PostgreSQL istnieją, ale pipeline trzyma wyniki w pamięci.
- `questionnaire_results` zapisuje wynik LLM, lecz endpoint wyniku odczytuje dane z `PlanningService`.
- `CostWeights` wspiera wagi czasu i pieniędzy, ale główny pipeline ustawia obie na zero.
- Bezpośredni `POST /planning` uruchamia wybór trasy, ale nie wykonuje końcowego etapu Directions i ticket pricing używanego przez flow użytkownika.
