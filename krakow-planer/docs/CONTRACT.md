# KONTRAKT: odpowiedź POST /api/plan

Plik jest jedynym źródłem prawdy o formacie. Nie zmieniaj nazw pól, typów ani
kolejności współrzędnych bez uzgodnienia z drugą osobą. Jeśli potrzebujesz
nowego pola, zaproponuj je i zaktualizuj ten plik oraz mock_plan.json w tym
samym commicie.

## Konwencje (obowiązują wszędzie)
- Współrzędne: ZAWSZE [lat, lng] (kolejność Leaflet). NIE [lng, lat] z GeoJSON/OSRM.
  Odwracanie robi backend w jednym miejscu (klient routingu).
- Czas: ISO 8601 ze strefą, Europe/Warsaw, np. "2026-10-10T09:00:00+02:00".
- Dystans: metry (int/float). Czas trwania: minuty. Pieniądze: PLN (float).
- Wartość nieznana = null (nie pomijaj pola, nie wpisuj "" ani 0 zamiast null).
- Zakres Krakowa (walidacja zdrowego rozsądku): lat ok. 49.97-50.13, lng ok. 19.79-20.07.
  Punkt poza zakresem = prawdopodobnie odwrócone współrzędne.

## Szablon odpowiedzi

```jsonc
{
  "request_id": "string",                  // unikalne id zapytania
  "proposals": [                           // 1-4 elementów; na MVP jeden
    {
      "label": "A|B|C|D",                  // A najtańsza, B najszybsza, C najwięcej atrakcji, D najmniej zatłoczona
      "strategy": "cheapest|fastest|most_sights|least_crowded",
      "title": "string",                   // nazwa dla użytkownika, po polsku
      "summary": {
        "total_cost_pln": 0.0,             // suma price_pln wszystkich stops + cost_pln wszystkich legs
        "total_duration_min": 0,           // od departure_at stopu start do arrival_at stopu end
        "total_distance_m": 0,             // suma distance_m wszystkich legs
        "total_walking_m": 0,              // suma distance_m legs z mode == "walk"
        "attractions_count": 0,            // liczba stops z kind == "attraction"
        "fits_time": true,                 // arrival_at stopu end <= end_at z requestu
        "fits_budget": true,               // total_cost_pln <= budget_pln z requestu
        "time_over_min": 0,                // max(0, o ile plan przekracza end_at), inaczej 0
        "budget_over_pln": 0.0             // max(0, o ile przekracza budżet), inaczej 0
      },
      "stops": [                           // posortowane rosnąco po order
        {
          "id": "string",                  // unikalne w propozycji, np. "s0", "s1"
          "order": 0,                      // 0,1,2,... bez dziur; 0 = start
          "kind": "start|attraction|end",  // pierwszy stop = start, ostatni = end
          "place": {
            "id": "string|null",           // id atrakcji z bazy; null dla start/end
            "name": "string",
            "lat": 0.0,
            "lng": 0.0,
            "category": "string|null",     // np. museum, food, park; null dla start/end
            "district": "string|null",
            "address": "string|null",
            "crowd_level": "low|medium|high|null",
            "sponsored": false             // tylko demo restauracji
          },
          "arrival_at": "ISO|null",        // null dla start
          "departure_at": "ISO|null",      // null dla end
          "visit_duration_min": 0,         // 0 dla start/end
          "price_pln": 0.0                 // bilet/wejście; 0 jeśli darmowe
        }
      ],
      "legs": [                            // odcinki między KOLEJNYMI stops
        {
          "id": "string",
          "from_stop_id": "string",        // id stopu z listy stops
          "to_stop_id": "string",          // id kolejnego stopu
          "mode": "walk|bus|bike|scooter|taxi|car",
          "distance_m": 0,
          "duration_min": 0,
          "cost_pln": 0.0,                 // bilet MPK / taxi / paliwo; 0 dla pieszo
          "coords": [[0.0, 0.0]]           // ścieżka po ulicach, [lat,lng], min. 2 punkty
        }
      ],
      "warnings": [
        {
          "code": "TIME_EXCEEDED|BUDGET_EXCEEDED|ATTRACTION_CLOSED|ROUTING_FALLBACK|NO_ROUTE|WEATHER",
          "message": "string",            // po polsku, czytelne dla użytkownika
          "stop_id": "string|null"
        }
      ]
    }
  ],
  "weather": null                          // na MVP zawsze null (priorytet 4)
}
```

## Niezmienniki (backend MUSI je spełniać, front może na nich polegać)
1. legs.length == stops.length - 1, i-ty leg łączy stops[i] -> stops[i+1].
2. from_stop_id / to_stop_id zawsze wskazują istniejące stops.id.
3. stops[0].kind == "start", ostatni == "end", reszta == "attraction".
4. arrival_at każdego stopu >= departure_at poprzedniego + czas przejazdu.
5. summary jest policzone z stops i legs (nie "z głowy"); fits_* zgodne z requestem.
6. Jeśli routing zawiedzie: coords = [start_punkt, koniec_punkt] (prosta linia)
   + warning ROUTING_FALLBACK. Nigdy puste coords i nigdy 500 z całym planem.
7. Jeśli plan się nie mieści w czasie/budżecie: backend sam wyrzuca najmniej
   wartościowe atrakcje, dodaje warning TIME_EXCEEDED/BUDGET_EXCEEDED i zwraca
   plan mieszczący się w limitach. Jeśli nawet minimalny plan się nie mieści:
   fits_time/fits_budget = false i odpowiedni warning.

## Czego NIE robić
- Nie zwracaj współrzędnych jako [lng, lat].
- Nie zwracaj dat bez strefy ani w innym formacie.
- Nie wprowadzaj pól spoza kontraktu "po cichu".

---

# KONTRAKT: konfiguracja (wejście do POST /api/plan)

```jsonc
{
  "start_at": "ISO",                  // początek wycieczki
  "end_at": "ISO",                    // twardy limit czasowy
  "start_location": {"name": "string", "lat": 0.0, "lng": 0.0},
  "end_location": null,               // null = wróć do start_location
  "budget_pln": 0.0,                  // twardy limit budżetu
  "preferred_categories": ["museum", "park"],  // z listy kategorii w bazie
  "food_preferences": ["polish", "vegan"],     // puste = brak preferencji
  "transport_modes": ["walk", "bus"],          // dozwolone środki
  "prefer_walking": true,
  "avoid_crowds": false,
  "weather_sensitive": false,
  "optimization_strategy": "cheapest|fastest|most_sights|least_crowded"
}
```

Brakujące pola uzupełnia backend wartościami domyślnymi (nie 422). Nieznane
kategorie są ignorowane z warningiem.

---

# Typy TypeScript (front)

```ts
export type Mode = "walk" | "bus" | "bike" | "scooter" | "taxi" | "car";
export type Strategy = "cheapest" | "fastest" | "most_sights" | "least_crowded";

export interface Place {
  id?: string | null; name: string; lat: number; lng: number;
  category: string | null; district?: string | null; address?: string | null;
  crowd_level?: "low" | "medium" | "high" | null; sponsored?: boolean;
}
export interface Stop {
  id: string; order: number; kind: "start" | "attraction" | "end";
  place: Place; arrival_at: string | null; departure_at: string | null;
  visit_duration_min: number; price_pln: number;
}
export interface Leg {
  id: string; from_stop_id: string; to_stop_id: string; mode: Mode;
  distance_m: number; duration_min: number; cost_pln: number;
  coords: [number, number][];
}
export interface Summary {
  total_cost_pln: number; total_duration_min: number; total_distance_m: number;
  total_walking_m: number; attractions_count: number;
  fits_time: boolean; fits_budget: boolean; time_over_min: number; budget_over_pln: number;
}
export interface Proposal {
  label: "A" | "B" | "C" | "D"; strategy: Strategy; title: string;
  summary: Summary; stops: Stop[]; legs: Leg[];
  warnings: { code: string; message: string; stop_id: string | null }[];
}
export interface PlanResponse {
  request_id: string; proposals: Proposal[];
  weather: { checked: boolean; condition: string; temp_c: number; affected_stop_ids: string[] } | null;
}
```

# Modele Pydantic (backend)

```python
from typing import Literal, Optional
from pydantic import BaseModel

Mode = Literal["walk", "bus", "bike", "scooter", "taxi", "car"]

class Place(BaseModel):
    id: Optional[str] = None
    name: str
    lat: float
    lng: float
    category: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    crowd_level: Optional[Literal["low", "medium", "high"]] = None
    sponsored: bool = False

class Stop(BaseModel):
    id: str
    order: int
    kind: Literal["start", "attraction", "end"]
    place: Place
    arrival_at: Optional[str] = None
    departure_at: Optional[str] = None
    visit_duration_min: int = 0
    price_pln: float = 0

class Leg(BaseModel):
    id: str
    from_stop_id: str
    to_stop_id: str
    mode: Mode
    distance_m: float
    duration_min: float
    cost_pln: float
    coords: list[tuple[float, float]]

class Warning(BaseModel):
    code: str
    message: str
    stop_id: Optional[str] = None

class Summary(BaseModel):
    total_cost_pln: float
    total_duration_min: float
    total_distance_m: float
    total_walking_m: float
    attractions_count: int
    fits_time: bool
    fits_budget: bool
    time_over_min: float = 0
    budget_over_pln: float = 0

class Proposal(BaseModel):
    label: Literal["A", "B", "C", "D"]
    strategy: Literal["cheapest", "fastest", "most_sights", "least_crowded"]
    title: str
    summary: Summary
    stops: list[Stop]
    legs: list[Leg]
    warnings: list[Warning] = []

class PlanResponse(BaseModel):
    request_id: str
    proposals: list[Proposal]
    weather: Optional[dict] = None
```
