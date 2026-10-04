"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from "react";
import {
  GeoJSON,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import L, { type LatLngExpression, type PathOptions } from "leaflet";
import {
  ArrowDown,
  ArrowUp,
  Bike,
  BusFront,
  CarFront,
  Clock3,
  Footprints,
  Route,
  Wallet,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getIcon } from "@/components/map/icons";
import type { Leg, RoutePlan, Stop } from "@/types/plan";

const KRAKOW_CENTER: LatLngExpression = [50.0647, 19.945];

const legStyles: Record<Leg["mode"], PathOptions> = {
  walk: { color: "#16845b", weight: 5, dashArray: "9 9", opacity: 0.9 },
  bus: { color: "#2563eb", weight: 6, opacity: 0.92 },
  bike: { color: "#ea8a16", weight: 5, opacity: 0.92 },
  scooter: { color: "#ea8a16", weight: 5, dashArray: "4 6", opacity: 0.92 },
  taxi: { color: "#dc2626", weight: 5, opacity: 0.92 },
  car: { color: "#dc2626", weight: 5, opacity: 0.92 },
};

function FitRoute({ points }: { points: LatLngExpression[] }) {
  const map = useMap();

  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
    }
  }, [map, points]);

  return null;
}

function SelectStopOnMap({
  selectedStopId,
  selectionVersion,
  markers,
}: {
  selectedStopId: string | null;
  selectionVersion: number;
  markers: MutableRefObject<Record<string, L.Marker | null>>;
}) {
  const map = useMap();

  useEffect(() => {
    if (!selectedStopId) return;
    const marker = markers.current[selectedStopId];
    if (!marker) return;
    const position = marker.getLatLng();
    map.flyTo(position, Math.max(map.getZoom(), 15), { duration: 0.45 });
    marker.openPopup();
  }, [map, markers, selectedStopId, selectionVersion]);

  return null;
}

function StopMarker({
  stop,
  setMarker,
}: {
  stop: Stop;
  setMarker: (id: string, marker: L.Marker | null) => void;
}) {
  const position: LatLngExpression = [stop.place.lat, stop.place.lng];
  return (
    <Marker
      position={position}
      icon={getIcon(stop.place.category, stop.kind, stop.order)}
      ref={(marker) => setMarker(stop.id, marker)}
    >
      <Popup>
        <div className="min-w-40 space-y-1 text-slate-800">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
            {stop.kind === "start"
              ? "Początek"
              : stop.kind === "end"
                ? "Koniec"
                : `Przystanek ${stop.order}`}
          </p>
          <p className="font-semibold">{stop.place.name}</p>
          <p className="text-sm text-slate-600">
            Przyjazd: {stop.arrival_at ? formatTime(stop.arrival_at) : "—"}
          </p>
          {stop.kind === "attraction" && (
            <p className="text-sm text-slate-600">
              Bilet: {stop.price_pln.toFixed(2)} zł
            </p>
          )}
          {stop.closes_at && (
            <p className="text-sm text-slate-600">
              Zamknięcie: {formatTime(stop.closes_at)}
            </p>
          )}
          {stop.warnings.map((warning) => (
            <p key={warning.code} className="text-sm font-semibold text-amber-700">
              {warning.message}
            </p>
          ))}
        </div>
      </Popup>
    </Marker>
  );
}

function RouteLine({ leg }: { leg: Leg }) {
  const popup = (
    <Popup>
      <div className="space-y-1 text-slate-800">
        <p className="font-semibold">{modeLabel(leg.mode)}</p>
        <p>
          {formatDistance(leg.distance_m)} · {Math.round(leg.duration_min)} min
        </p>
        <p>{leg.cost_pln.toFixed(2)} zł</p>
      </div>
    </Popup>
  );

  if (leg.geometry) {
    return (
      <GeoJSON data={leg.geometry} pathOptions={legStyles[leg.mode]}>
        {popup}
      </GeoJSON>
    );
  }

  return (
    <Polyline positions={leg.coords} pathOptions={legStyles[leg.mode]}>
      {popup}
    </Polyline>
  );
}

function modeLabel(mode: Leg["mode"]) {
  return {
    walk: "Pieszo",
    bus: "Komunikacja miejska",
    bike: "Rower",
    scooter: "Hulajnoga",
    taxi: "Taksówka",
    car: "Samochód",
  }[mode];
}

function TransportModeIcon({ mode }: { mode: Leg["mode"] }) {
  if (mode === "walk") {
    return <Footprints className="size-3.5" aria-hidden="true" />;
  }

  if (mode === "bus") {
    return <BusFront className="size-3.5" aria-hidden="true" />;
  }

  if (mode === "bike" || mode === "scooter") {
    return <Bike className="size-3.5" aria-hidden="true" />;
  }

  return <CarFront className="size-3.5" aria-hidden="true" />;
}

function formatDistance(meters: number) {
  return meters >= 1000
    ? `${(meters / 1000).toFixed(1)} km`
    : `${Math.round(meters)} m`;
}

function formatDuration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return hours > 0 ? `${hours} godz. ${remainder} min` : `${remainder} min`;
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("pl-PL", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function TripMap({ plan }: { plan: RoutePlan }) {
  const markers = useRef<Record<string, L.Marker | null>>({});
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const [selectionVersion, setSelectionVersion] = useState(0);
  const routePoints = useMemo<LatLngExpression[]>(() => {
    const legPoints = plan.legs.flatMap((leg) =>
      leg.coords.map(([lat, lng]) => [lat, lng] as LatLngExpression),
    );
    return legPoints.length > 0
      ? legPoints
      : plan.stops.map(
          (stop) => [stop.place.lat, stop.place.lng] as LatLngExpression,
        );
  }, [plan.legs, plan.stops]);
  const totalTravelDurationMin = useMemo(
    () => plan.legs.reduce((total, leg) => total + leg.duration_min, 0),
    [plan.legs],
  );
  const setMarker = (id: string, marker: L.Marker | null) => {
    markers.current[id] = marker;
  };

  return (
    <div className="w-full rounded-[2rem] bg-[#f4f7f3] px-4 py-6 text-slate-900 shadow-[0_24px_70px_rgba(63,143,177,0.12)] sm:px-6 lg:px-10">
      <div className="mx-auto max-w-[1500px]">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">
              Kraków · Twój plan dnia
            </p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Twój plan po Krakowie
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              Trasa zaplanowana wokół Twoich zainteresowań, czasu i tempa.
            </p>
          </div>
        </header>

        {plan.solver_status === "timeout" && (
          <div
            role="status"
            className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
          >
            <span className="font-semibold">
              Nie udało się potwierdzić optymalnej trasy.{" "}
            </span>
            Pokazujemy najlepszy plan znaleziony przed upływem limitu czasu.
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_370px]">
          <section
            aria-label="Mapa planu wycieczki"
            className="overflow-hidden rounded-3xl border border-emerald-950/10 bg-white p-2 shadow-sm"
          >
            <MapContainer
              center={KRAKOW_CENTER}
              zoom={13}
              scrollWheelZoom
              className="h-[460px] w-full rounded-2xl sm:h-[600px]"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <FitRoute points={routePoints} />
              <SelectStopOnMap
                selectedStopId={selectedStopId}
                selectionVersion={selectionVersion}
                markers={markers}
              />
              {plan.legs.map((leg) => (
                <RouteLine key={leg.id} leg={leg} />
              ))}
              {plan.stops.map((stop) => (
                <StopMarker key={stop.id} stop={stop} setMarker={setMarker} />
              ))}
            </MapContainer>
            <div className="flex flex-wrap gap-x-5 gap-y-2 px-3 py-3 text-xs text-slate-600">
              <span className="inline-flex items-center gap-2">
                <i className="h-0.5 w-6 border-t-2 border-dashed border-emerald-700" />
                Pieszo
              </span>
              <span className="inline-flex items-center gap-2">
                <i className="h-1 w-6 rounded bg-blue-600" /> Komunikacja
              </span>
              <span className="inline-flex items-center gap-2">
                <i className="h-1 w-6 rounded bg-[#ea8a16]" /> Rower
              </span>
              <span className="inline-flex items-center gap-2">
                <i className="h-3 w-3 rounded-full border-2 border-blue-700 bg-blue-100" />
                Numerowany przystanek
              </span>
            </div>
          </section>

          <aside className="space-y-4">
            <Card className="rounded-3xl border-emerald-950/10 shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Podsumowanie</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  <Metric
                    icon={<Wallet size={17} />}
                    label="Koszt"
                    value={`${plan.summary.total_cost_pln.toFixed(0)} zł`}
                  />
                  <Metric
                    icon={<Wallet size={17} />}
                    label="Budżet"
                    value={`${plan.budget_pln.toFixed(0)} zł`}
                    detail={
                      plan.summary.fits_budget === null ? undefined : plan.summary.fits_budget ? (
                        <span className="flex items-center gap-1 text-xs font-semibold text-emerald-700">
                          <ArrowUp className="size-3.5" aria-hidden="true" />
                          {Math.max(0, plan.budget_pln - plan.summary.total_cost_pln).toFixed(0)} zł zapasu
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs font-semibold text-red-600">
                          <ArrowDown className="size-3.5" aria-hidden="true" />
                          {(plan.summary.budget_over_pln ?? Math.max(0, plan.summary.total_cost_pln - plan.budget_pln)).toFixed(0)} zł ponad budżet
                        </span>
                      )
                    }
                  />
                  <Metric
                    icon={<Clock3 size={17} />}
                    label="Czas"
                    value={formatDuration(plan.summary.total_duration_min)}
                  />
                  <Metric
                    icon={<Route size={17} />}
                    label="Czas dojazdów"
                    value={formatDuration(totalTravelDurationMin)}
                  />
                  <Metric
                    icon={<Footprints size={17} />}
                    label="Dystans"
                    value={formatDistance(plan.summary.total_distance_m)}
                  />
                  <Metric
                    icon={<Footprints size={17} />}
                    label="Pieszo"
                    value={formatDistance(plan.summary.total_walking_m)}
                  />
                </div>
                <p className="mt-4 border-t border-slate-100 pt-3 text-sm text-slate-600">
                  {plan.summary.attractions_count} atrakcji na trasie
                </p>
                {(plan.summary.fits_time === false ||
                  plan.summary.fits_budget === false) && (
                  <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800">
                    {plan.summary.fits_time === false && (
                      <p>
                        Plan przekracza dostępny czas o {plan.summary.time_over_min} min.
                      </p>
                    )}
                    {plan.summary.fits_budget === false &&
                      plan.summary.budget_over_pln !== null && (
                        <p>
                          Plan przekracza budżet o {plan.summary.budget_over_pln.toFixed(2)} zł.
                        </p>
                      )}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="rounded-3xl border-emerald-950/10 shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Twoje przystanki</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-1">
                  {plan.stops.map((stop, index) => {
                    const nextStop = plan.stops[index + 1];
                    const nextLeg = nextStop
                      ? plan.legs.find(
                          (leg) =>
                            leg.from_stop_id === stop.id &&
                            leg.to_stop_id === nextStop.id,
                        ) ?? plan.legs[index]
                      : undefined;

                    return (
                      <li key={stop.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedStopId(stop.id);
                            setSelectionVersion((version) => version + 1);
                          }}
                          className="group flex w-full items-start gap-3 rounded-xl p-2.5 text-left transition hover:bg-emerald-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
                        >
                          <span className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${stop.kind === "start" ? "bg-emerald-100 text-emerald-800" : stop.kind === "end" ? "bg-amber-100 text-amber-800" : "bg-blue-100 text-blue-800"}`}>
                            {stop.kind === "start" ? "S" : stop.kind === "end" ? "K" : stop.order}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-semibold group-hover:text-emerald-800">{stop.place.name}</span>
                            <span className="mt-0.5 block text-xs text-slate-500">
                              {stop.arrival_at ? new Date(stop.arrival_at).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" }) : "Start"}
                              {stop.kind === "attraction" &&
                                ` · ${
                                  !stop.ticket_price_known
                                    ? "cena nieznana"
                                    : stop.price_pln
                                      ? `${stop.price_pln.toFixed(0)} zł`
                                      : "bezpłatnie"
                                }`}
                            </span>
                            {stop.closes_at && (
                              <span className="mt-0.5 block text-xs text-slate-500">
                                Otwarte do {formatTime(stop.closes_at)}
                              </span>
                            )}
                            {stop.warnings.length > 0 && (
                              <span className="mt-1 block text-xs font-semibold text-amber-700">
                                {stop.warnings[0].message}
                              </span>
                            )}
                          </span>
                        </button>

                        {nextLeg && (
                          <div
                            className="ml-6 flex min-h-9 items-center gap-2 border-l-2 border-dashed border-slate-200 pl-5 text-xs font-semibold text-slate-500"
                            aria-label={`${modeLabel(nextLeg.mode)}, ${formatDuration(nextLeg.duration_min)}`}
                          >
                            <span className="flex size-6 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                              <TransportModeIcon mode={nextLeg.mode} />
                            </span>
                            <span>{formatDuration(nextLeg.duration_min)}</span>
                            <span aria-hidden="true">·</span>
                            <span>{modeLabel(nextLeg.mode)}</span>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ol>
              </CardContent>
            </Card>

            {plan.warnings.length > 0 && (
              <div className="space-y-2" aria-label="Ostrzeżenia">
                {plan.warnings.map((warning, index) => (
                  <div key={`${warning.code}-${index}`} role="status" className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
                    <span className="font-semibold">Informacja · </span>{warning.message}
                  </div>
                ))}
              </div>
            )}
          </aside>
        </div>
        <p className="mt-5 text-xs text-slate-500">Mapa © OpenStreetMap contributors</p>
      </div>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: ReactNode;
}) {
  return (
    <div className="rounded-2xl bg-[#f4f7f3] p-3">
      <div className="flex items-center gap-1.5 text-emerald-800">{icon}<span className="text-xs font-medium text-slate-600">{label}</span></div>
      <p className="mt-1.5 text-base font-semibold tabular-nums">{value}</p>
      {detail ? <div className="mt-1">{detail}</div> : null}
    </div>
  );
}
