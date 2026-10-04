import Link from "next/link";
import {
  ArrowRight,
  Check,
  Clock3,
  Coffee,
  Footprints,
  Map,
  MapPin,
  Route,
  SlidersHorizontal,
  Sparkles,
  Ticket,
} from "lucide-react";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";

const steps = [
  {
    number: "01",
    icon: SlidersHorizontal,
    title: "Powiedz, czego szukasz",
    description:
      "Wybierz tempo, budżet i opowiedz nam krótko o swoich zainteresowaniach.",
  },
  {
    number: "02",
    icon: Sparkles,
    title: "Daj nam chwilę",
    description:
      "Łączymy miejsca, godziny otwarcia i dojazdy w jedną sensowną trasę.",
  },
  {
    number: "03",
    icon: Route,
    title: "Ruszaj w miasto",
    description:
      "Dostajesz gotowy plan na mapie — z czasem, kosztem i kolejnością przystanków.",
  },
];

const benefits = [
  {
    icon: Clock3,
    title: "Bez straty czasu",
    text: "Plan, który naprawdę mieści się w Twoim dniu.",
  },
  {
    icon: Ticket,
    title: "Budżet pod kontrolą",
    text: "Koszty biletów i przejazdów w jednym miejscu.",
  },
  {
    icon: Footprints,
    title: "Trasa, nie lista",
    text: "Kolejność miejsc dopasowana do poruszania się po mieście.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#f3fbff] text-[#17364d]">
      <div className="relative">
        <div className="pointer-events-none absolute -top-28 -left-40 size-[30rem] rounded-full bg-[#75ddff]/30 blur-3xl" />
        <div className="pointer-events-none absolute top-20 -right-52 size-[34rem] rounded-full bg-[#b8efff]/55 blur-3xl" />
        <SiteHeader active="landing" />

        <section className="relative z-10 mx-auto grid w-full max-w-7xl items-center gap-14 px-5 pt-14 pb-24 sm:px-8 sm:pt-20 lg:grid-cols-[1.02fr_0.98fr] lg:px-10 lg:pt-24 lg:pb-32">
          <div className="max-w-2xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#c9eaf6] bg-white/80 px-4 py-2 text-xs font-extrabold tracking-wide text-[#158fbe] shadow-sm backdrop-blur">
              <Sparkles className="size-4" aria-hidden="true" />
              KRAKÓW W TWOIM RYTMIE
            </div>
            <h1 className="text-5xl leading-[1.02] font-extrabold tracking-[-0.055em] text-[#153047] sm:text-6xl lg:text-7xl">
              Miasto ma tysiąc dróg.
              <span className="relative mt-2 block text-[#2db9ee]">
                Ty potrzebujesz jednej.
                <svg
                  viewBox="0 0 420 18"
                  className="absolute -bottom-4 left-0 h-4 w-full max-w-[420px] text-[#86ddf8]"
                  aria-hidden="true"
                >
                  <path
                    d="M3 12C93 2 260 2 417 9"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="6"
                    strokeLinecap="round"
                  />
                </svg>
              </span>
            </h1>
            <p className="mt-9 max-w-xl text-lg leading-8 text-[#5c778b] sm:text-xl">
              VentureFlux zamienia Twoje zainteresowania, czas i budżet w gotowy plan zwiedzania Krakowa — bez godzin spędzonych nad mapą.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/planner"
                className="group inline-flex h-14 items-center justify-center gap-2 rounded-full bg-[#2db9ee] px-7 text-base font-extrabold text-white shadow-[0_14px_34px_rgba(45,185,238,0.3)] transition hover:-translate-y-0.5 hover:bg-[#169fd5] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#2db9ee]/25"
              >
                Ułóż mój dzień
                <ArrowRight className="size-5 transition group-hover:translate-x-1" aria-hidden="true" />
              </Link>
              <Link
                href="/home"
                className="inline-flex h-14 items-center justify-center rounded-full border border-[#c8e3ee] bg-white/80 px-7 text-base font-extrabold text-[#35556c] shadow-sm transition hover:border-[#8ed5ee] hover:bg-white focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#2db9ee]/20"
              >
                Zobacz aplikację
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-semibold text-[#668094]">
              {["Plan w kilka minut", "Dopasowany budżet", "Gotowa mapa trasy"].map((item) => (
                <span key={item} className="flex items-center gap-2">
                  <span className="flex size-5 items-center justify-center rounded-full bg-[#dff6fe] text-[#1aa6da]">
                    <Check className="size-3" aria-hidden="true" />
                  </span>
                  {item}
                </span>
              ))}
            </div>
          </div>

          <HeroRouteCard />
        </section>
      </div>

      <section className="relative z-10 border-y border-[#dceef6] bg-white/70">
        <div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-px px-5 sm:grid-cols-3 sm:px-8 lg:px-10">
          {benefits.map(({ icon: Icon, title, text }) => (
            <div key={title} className="flex items-start gap-4 px-2 py-8 sm:px-6 lg:px-10">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-[#e4f7fe] text-[#1da9de]">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <div>
                <h2 className="font-extrabold text-[#214158]">{title}</h2>
                <p className="mt-1 text-sm leading-6 text-[#71899a]">{text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-5 py-24 sm:px-8 lg:px-10 lg:py-32">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-extrabold tracking-[0.2em] text-[#1799cb] uppercase">Jak to działa</p>
          <h2 className="mt-4 text-3xl font-extrabold tracking-[-0.04em] text-[#17364d] sm:text-5xl">
            Od pomysłu do gotowej trasy
          </h2>
          <p className="mt-4 text-base leading-7 text-[#668094]">
            Ty wybierasz kierunek. My zajmujemy się całą logistyką.
          </p>
        </div>
        <div className="mt-14 grid gap-5 lg:grid-cols-3">
          {steps.map(({ number, icon: Icon, title, description }) => (
            <article
              key={number}
              className="group relative overflow-hidden rounded-[2rem] border border-white bg-white/90 p-7 shadow-[0_18px_50px_rgba(63,143,177,0.10)] transition hover:-translate-y-1 hover:shadow-[0_24px_60px_rgba(63,143,177,0.16)] sm:p-8"
            >
              <span className="absolute top-4 right-6 text-6xl font-black tracking-[-0.08em] text-[#edf8fc]">{number}</span>
              <span className="relative flex size-13 items-center justify-center rounded-2xl bg-[#2db9ee] text-white shadow-[0_10px_26px_rgba(45,185,238,0.24)]">
                <Icon className="size-6" aria-hidden="true" />
              </span>
              <h3 className="relative mt-7 text-xl font-extrabold tracking-[-0.025em]">{title}</h3>
              <p className="relative mt-3 text-sm leading-7 text-[#668094]">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="px-5 pb-24 sm:px-8 lg:px-10 lg:pb-32">
        <div className="relative mx-auto max-w-7xl overflow-hidden rounded-[2.5rem] bg-[#17364d] px-7 py-14 text-white shadow-[0_30px_80px_rgba(23,54,77,0.2)] sm:px-12 lg:flex lg:items-center lg:justify-between lg:px-16 lg:py-16">
          <div className="pointer-events-none absolute -top-28 -right-24 size-72 rounded-full border-[40px] border-[#2db9ee]/15" />
          <div className="relative max-w-2xl">
            <p className="text-xs font-extrabold tracking-[0.18em] text-[#79dfff] uppercase">Kraków czeka</p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-[-0.04em] sm:text-4xl">
              Jeden dzień. Plan, który do Ciebie pasuje.
            </h2>
            <p className="mt-4 leading-7 text-[#bdd0dc]">Zacznij od kilku prostych pytań, a resztę ułożymy za Ciebie.</p>
          </div>
          <Link
            href="/planner"
            className="group relative mt-8 inline-flex h-14 shrink-0 items-center justify-center gap-2 rounded-full bg-white px-7 font-extrabold text-[#17364d] transition hover:-translate-y-0.5 hover:bg-[#e8f8ff] lg:mt-0"
          >
            Rozpocznij planowanie
            <ArrowRight className="size-5 transition group-hover:translate-x-1" aria-hidden="true" />
          </Link>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}

function HeroRouteCard() {
  const stops = [
    { time: "10:00", title: "Rynek Główny", icon: MapPin, tone: "bg-[#dff6fe] text-[#159dcc]" },
    { time: "12:15", title: "Kazimierz", icon: Coffee, tone: "bg-[#fff3d8] text-[#ca7a12]" },
    { time: "15:30", title: "Wawel", icon: Map, tone: "bg-[#e5f7ea] text-[#278556]" },
  ];

  return (
    <div className="relative mx-auto w-full max-w-xl lg:ml-auto">
      <div className="absolute -top-8 -right-6 hidden rounded-2xl bg-white px-4 py-3 shadow-[0_15px_40px_rgba(38,106,136,0.16)] sm:flex sm:items-center sm:gap-3">
        <span className="flex size-9 items-center justify-center rounded-xl bg-[#e5f8ff] text-[#1ba7db]">
          <Clock3 className="size-4" aria-hidden="true" />
        </span>
        <span>
          <span className="block text-[10px] font-bold text-[#8299a8] uppercase">Czas trasy</span>
          <span className="text-sm font-extrabold">6 godz. 20 min</span>
        </span>
      </div>
      <div className="absolute -bottom-7 -left-7 hidden rounded-2xl bg-[#17364d] px-4 py-3 text-white shadow-[0_16px_42px_rgba(23,54,77,0.25)] sm:flex sm:items-center sm:gap-3">
        <Ticket className="size-5 text-[#73dfff]" aria-hidden="true" />
        <span>
          <span className="block text-[10px] font-bold text-[#a8c3d2] uppercase">W budżecie</span>
          <span className="text-sm font-extrabold">86 zł / 100 zł</span>
        </span>
      </div>

      <div className="rotate-[1.5deg] rounded-[2.3rem] border border-white/90 bg-white/92 p-4 shadow-[0_32px_90px_rgba(42,123,157,0.20)] backdrop-blur sm:p-6">
        <div className="overflow-hidden rounded-[1.7rem] bg-[#eaf7f5]">
          <div className="relative h-40 sm:h-52">
            <div
              className="absolute inset-0 opacity-40"
              style={{
                backgroundImage:
                  "linear-gradient(#a9d6d3 1px, transparent 1px), linear-gradient(90deg, #a9d6d3 1px, transparent 1px)",
                backgroundSize: "34px 34px",
              }}
            />
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 520 210" fill="none" aria-hidden="true">
              <path d="M48 169C113 125 127 55 218 86C302 114 332 28 464 47" stroke="#2db9ee" strokeWidth="7" strokeLinecap="round" strokeDasharray="11 12" />
              <circle cx="48" cy="169" r="13" fill="white" stroke="#2db9ee" strokeWidth="6" />
              <circle cx="218" cy="86" r="13" fill="white" stroke="#2db9ee" strokeWidth="6" />
              <circle cx="464" cy="47" r="13" fill="#17364d" stroke="white" strokeWidth="6" />
            </svg>
            <span className="absolute top-4 left-4 rounded-full bg-white/90 px-3 py-1.5 text-xs font-extrabold text-[#35556c] shadow-sm">Twój plan na dziś</span>
          </div>
        </div>
        <div className="px-2 pt-6 pb-2">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold tracking-wide text-[#159dcc] uppercase">Kraków · 3 przystanki</p>
              <h2 className="mt-1 text-xl font-extrabold tracking-[-0.03em]">Dzień pełen odkryć</h2>
            </div>
            <span className="flex size-10 items-center justify-center rounded-full bg-[#e6f8fe] text-[#18a3d7]">
              <Route className="size-5" aria-hidden="true" />
            </span>
          </div>
          <div className="space-y-2">
            {stops.map(({ time, title, icon: Icon, tone }) => (
              <div key={title} className="flex items-center gap-3 rounded-2xl bg-[#f7fbfd] p-3">
                <span className={`flex size-10 items-center justify-center rounded-xl ${tone}`}>
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-bold text-[#8299a8]">{time}</p>
                  <p className="truncate text-sm font-extrabold text-[#294a61]">{title}</p>
                </div>
                <ArrowRight className="size-4 text-[#9bb0bd]" aria-hidden="true" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
