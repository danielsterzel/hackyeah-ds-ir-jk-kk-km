# Prompty: BACKEND (FastAPI, algorytm trasy)

Przed każdym promptem wklej blok KONTEKST z `00_WSPOLNE.md`.
Fazę 0 (mock_plan.json) robicie razem, patrz `00_WSPOLNE.md`.

---

## FAZA 1: wersja minimum

### B1: endpoint i modele
```
Zadanie: w FastAPI zrób POST /api/plan, który przyjmuje konfigurację
(wejście z docs/CONTRACT.md) i na razie zwraca zawartość mock_plan.json.
Wymagania: modele Pydantic 1:1 z kontraktem (Place, Stop, Leg, Warning,
Summary, Proposal, PlanResponse), response_model ustawiony, CORS dla
localhost:3000, endpoint GET /health. Struktura: app/main.py, app/models.py,
app/routers/plan.py. Dodaj test sprawdzający, że mock waliduje się modelem.
Czego nie robić: żadnej bazy, żadnej logiki algorytmu na tym etapie.
```

### B2: dane atrakcji
```
Zadanie: przygotuj źródło atrakcji Krakowa jako data/attractions.json
(30-50 wpisów) + funkcję load_attractions().
Pola atrakcji: id, name, lat, lng, category, district, address,
visit_duration_min, price_pln, crowd_level, opening_hours (prosty format:
dni + godziny otwarcia/zamknięcia), sponsored (domyślnie false).
Wymagania: realne współrzędne w obrębie Krakowa, kategorie z jednej
stałej listy (museum, park, food, monument, viewpoint, ...),
walidacja modelem Pydantic przy starcie.
Czego nie robić: nie podłączaj jeszcze Supabase, KISS.
```

### B3: klient routingu
```
Zadanie: zrób moduł app/routing.py z funkcją
async get_leg(a: Place, b: Place, mode: str) -> dict
zwracającą {coords, distance_m, duration_min}.
Użyj OSRM (httpx, geometries=geojson, overview=full). Mapowanie mode ->
profil: walk=foot, bike=bike, car/taxi=car. Konfiguracja bazowego URL-a
z .env (OSRM_BASE_URL).
KRYTYCZNE: OSRM zwraca [lng,lat]; odwróć na [lat,lng] w tym jednym miejscu.
Fallback: przy błędzie/timeoucie zwróć coords=[[a.lat,a.lng],[b.lat,b.lng]]
z dystansem z haversine i czasem szacowanym z prędkości (piesza 5 km/h),
oraz flagą fallback=True (żeby wyższa warstwa dodała ROUTING_FALLBACK).
Dodaj cache w pamięci (klucz: współrzędne+mode), timeout 5 s.
Dodaj testy: odwrócenie współrzędnych i fallback (mock httpx).
```

Uwaga praktyczna: publiczny serwer demo OSRM (`router.project-osrm.org`)
obsługuje tylko profil samochodowy i nie nadaje się do większego ruchu.
Do pieszo/rower sprawdź `routing.openstreetmap.de` (osobne endpointy
foot/bike) albo postaw własny OSRM z wycinkiem Małopolski (Docker).
Komunikacja miejska wymaga danych GTFS, na MVP można ją uprościć do
szacunku.

### B4: algorytm v1
```
Zadanie: zrób app/planner.py z funkcją
build_plan(config, attractions) -> Proposal.
Wersja 1 (KISS): 1) filtruj atrakcje wg preferred_categories, godzin
otwarcia i dostępności w oknie start_at-end_at; 2) wybierz atrakcje
zachłannie wg strategii (cheapest: najtańsze, most_sights: najkrótszy
czas zwiedzania na atrakcję); 3) ułóż kolejność nearest neighbour od
start_location; 4) policz arrival_at/departure_at przez get_leg;
5) jeśli przekracza end_at lub budget_pln - usuń najmniej opłacalną
atrakcję i licz od nowa, dopóki się mieści; 6) dodaj warnings.
Wymagania: summary liczone ściśle wg definicji z kontraktu, spełnione
wszystkie niezmienniki, funkcje czyste tam gdzie się da (łatwe testy).
Dodaj testy: plan mieści się w czasie i budżecie; plan niemożliwy daje
fits_*=false i warning; kolejność stopów ma sens.
Czego nie robić: OR-Tools/2-opt na tym etapie (to Faza 3).
```

### B5: integracja z LLM
```
Zadanie: zrób moduł app/llm.py, który bierze odpowiedzi z formularza
(tekst/JSON) i przez Ollama (HTTP localhost:11434) zwraca konfigurację
zgodną z kontraktem wejściowym. Wymuś JSON w odpowiedzi, sparsuj,
zwaliduj modelem Pydantic. Brakujące pola - wartości domyślne.
Fallback: jeśli LLM zwróci śmieci, użyj wartości domyślnych i dodaj
warning, nie rzucaj 500. Podepnij w POST /api/plan zamiast mocka:
config -> build_plan -> PlanResponse.
```

---

## FAZA 2: integracja
Patrz `00_WSPOLNE.md` (prompt "Back").

---

## FAZA 3: rozszerzenia

```
Zadanie: dodaj strategie B (fastest), C (most_sights), D (least_crowded)
i zwracaj kilka propozycji w proposals[] (A-D) w jednym zapytaniu.
Ulepsz kolejność trasy: 2-opt na bazie nearest neighbour (albo OR-Tools
TSP jeśli jest dostępne), z limitem czasu obliczeń. Dodaj prostą wersję
pogody (Open-Meteo, bez klucza): przy deszczu dodaj warning WEATHER
i preferuj atrakcje indoor. Nie łam istniejącego kontraktu - nowe pola
tylko opcjonalne i zapisane w docs/CONTRACT.md. Dodaj testy
regresyjne dla wcześniejszych scenariuszy.
```

---

## Instalacja (backend)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/Mac: source .venv/bin/activate)

pip install fastapi "uvicorn[standard]" pydantic httpx python-dotenv
pip install sqlalchemy alembic "psycopg[binary]" geoalchemy2 pgvector   # na MVP można pominąć
pip install numpy
pip install ortools             # opcjonalnie, do TSP/VRP (Faza 3)
pip install pytest
pip freeze > requirements.txt

uvicorn app.main:app --reload
```
