# Prompty: FRONTEND (Next.js, Leaflet, mapa)

Przed każdym promptem wklej blok KONTEKST z `00_WSPOLNE.md`.
Fazę 0 (mock_plan.json) robicie razem, patrz `00_WSPOLNE.md`.

---

## FAZA 1: wersja minimum

### F1: typy i szkielet mapy
```
Zadanie: w Next.js (App Router) dodaj typy z docs/CONTRACT.md
(src/types/plan.ts: Place, Stop, Leg, Summary, Proposal, PlanResponse)
oraz komponent mapy z react-leaflet.
Wymagania: TripMap.tsx ("use client") ładowany przez next/dynamic
z ssr:false (TripMapLoader.tsx); import "leaflet/dist/leaflet.css";
TileLayer OpenStreetMap z poprawnym attribution; kontener z jawną
wysokością (np. h-[600px]); środek mapy Kraków [50.0647, 19.945], zoom 13.
Dane na razie z lokalnego mock_plan.json. Strona /plan wyświetla mapę.
Czego nie robić: nie używaj domyślnych markerów Leaflet (psują się w Next).
```

### F2: markery z custom icons
```
Zadanie: zrób src/components/map/icons.tsx z funkcją getIcon(category)
zwracającą L.divIcon z ikoną lucide-react (renderToStaticMarkup).
Kategorie: museum, food, park, monument, viewpoint + fallback MapPin.
Osobny, wyraźny styl dla start i end. Kolor inline (nie dynamiczne klasy
Tailwind, bo ich nie wykryje). className:"" w divIcon, poprawne
iconSize/iconAnchor/popupAnchor.
Wyświetl Marker dla każdego stopu z mocka, Popup z numerem kolejności,
nazwą, godziną przyjazdu i ceną.
```

### F3: polyline
```
Zadanie: narysuj trasę z proposal.legs jako <Polyline> w react-leaflet.
Wymagania: styl zależny od mode (walk: zielona przerywana dashArray,
bus: niebieska, bike: pomarańczowa, car/taxi: czerwona), osobny Polyline
na każdy leg; coords są już [lat,lng], nie odwracaj ich na froncie.
Komponent FitBounds używający useMap().fitBounds() po wszystkich
punktach trasy (padding 40). Kliknięcie w polyline pokazuje Popup:
środek transportu, dystans, czas, koszt.
```

### F4: panel boczny
```
Zadanie: zrób panel obok mapy (shadcn Card, Badge, Alert): lista stopów
z numerem, nazwą, godzinami i ceną; blok summary (koszt, czas, dystans,
pieszo, liczba atrakcji); warnings jako Alert (variant dla ostrzeżeń).
Gdy fits_time lub fits_budget są false - widoczny czerwony komunikat.
Kliknięcie stopu na liście centruje mapę na nim (useMap + flyTo)
i otwiera popup. Responsywne: na mobile mapa nad panelem.
```

### F5: formularz i wywołanie API
```
Zadanie: zrób formularz konfiguracji (pola z kontraktu wejściowego)
w shadcn i podepnij TanStack Query (useMutation) do POST /api/plan.
Wymagania: QueryClientProvider w layout (client component), URL backendu
z NEXT_PUBLIC_API_URL, stany loading (skeleton/spinner), error
(czytelny komunikat, przycisk "spróbuj ponownie") i pustej odpowiedzi.
Po sukcesie render TripMap + panel z prawdziwymi danymi.
Zostaw przełącznik USE_MOCK=true, żebym mógł pracować bez backendu.
```

---

## FAZA 2: integracja
Patrz `00_WSPOLNE.md` (prompt "Front").

---

## FAZA 3: rozszerzenia

```
Zadanie: dodaj zakładki (shadcn Tabs) A/B/C/D przełączające propozycje
na mapie i w panelu, z porównaniem kluczowych metryk (koszt, czas,
liczba atrakcji) obok siebie. Dodaj legendę mapy (mode -> kolor linii,
kategoria -> ikona). Obsłuż weather (jeśli nie null): ikona/komunikat
i wyróżnienie affected_stop_ids. Zachowaj działanie przy proposals.length == 1.
```

---

## Instalacja (frontend)

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app

cd frontend
npm i leaflet react-leaflet
npm i -D @types/leaflet
npm i @tanstack/react-query
npm i lucide-react
npx shadcn@latest init
npx shadcn@latest add card button alert badge tabs
```

Uwaga na wersje: `react-leaflet` v5 wymaga Reacta 19 (nowe Next go ma).
Jeśli macie React 18, instalujcie `react-leaflet@4`.

Rozszerzenia VS Code (opcjonalnie): Python + Pylance, ESLint, Tailwind CSS
IntelliSense, Prettier.
