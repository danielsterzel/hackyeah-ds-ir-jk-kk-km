import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowRight,
  Clock3,
  Coffee,
  Compass,
  Footprints,
  Landmark,
  MapPin,
  Navigation,
  Route,
  Sparkles,
  Trees,
  WalletCards,
} from "lucide-react";

import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";

export const metadata: Metadata = {
  title: "Home",
  description: "Zacznij planować swój dzień w Krakowie z VentureFlux.",
};

const quickPlans = [
  {
    icon: Landmark,
    title: "Klasyki Krakowa",
    description: "Najważniejsze miejsca w dobrze ułożonej kolejności.",
    meta: "historia · architektura",
    color: "bg-[#e5f7fe] text-[#149dd0]",
  },
  {
    icon: Coffee,
    title: "Kawa i Kazimierz",
    description: "Spokojny spacer między zaułkami i dobrymi kawiarniami.",
    meta: "slow travel · jedzenie",
    color: "bg-[#fff3dc] text-[#c97913]",
  },
  {
    icon: Trees,
    title: "Zielony reset",
    description: "Parki, widoki i miejsca z dala od miejskiego zgiełku.",
    meta: "natura · bez tłumów",
    color: "bg-[#e7f7eb] text-[#33865a]",
  },
];

const facts = [
  { icon: Clock3, label: "Czas", value: "dopasowany" },
  { icon: WalletCards, label: "Budżet", value: "pod kontrolą" },
  { icon: Footprints, label: "Tempo", value: "w Twoim rytmie" },
];

export default function HomePage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#f3fbff] text-[#17364d]">
      <div className="relative">
        <div className="pointer-events-none absolute -top-36 right-[-8rem] size-[32rem] rounded-full bg-[#a6e9ff]/40 blur-3xl" />
        <div className="pointer-events-none absolute top-[28rem] -left-52 size-96 rounded-full bg-[#c8f2ff]/45 blur-3xl" />
        <SiteHeader active="home" />

        <section className="relative z-10 mx-auto w-full max-w-7xl px-5 pt-10 pb-24 sm:px-8 sm:pt-14 lg:px-10">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <p className="flex items-center gap-2 text-sm font-extrabold text-[#159dcc]">
                <MapPin className="size-4" aria-hidden="true" />
                Kraków
              </p>
              <h1 className="mt-3 text-4xl font-extrabold tracking-[-0.045em] text-[#17364d] sm:text-5xl">
                Dzień dobry! Gdzie dziś idziemy?
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-[#668094]">
                Zacznij od własnego pomysłu albo wybierz inspirację. Dopasujemy trasę do Ciebie.
              </p>
            </div>
            <div className="hidden items-center gap-2 rounded-full border border-[#d5eaf3] bg-white/80 px-4 py-2 text-xs font-bold text-[#5d7a8e] shadow-sm sm:flex">
              <span className="size-2 rounded-full bg-[#32c782]" />
              Planer gotowy
            </div>
          </div>

          <div className="mt-10 grid gap-6 lg:grid-cols-[1.42fr_0.58fr]">
            <section className="relative overflow-hidden rounded-[2.4rem] bg-[#17364d] px-7 py-9 text-white shadow-[0_26px_65px_rgba(23,54,77,0.18)] sm:px-10 sm:py-11">
              <div className="pointer-events-none absolute -top-28 -right-20 size-80 rounded-full border-[48px] border-[#2db9ee]/16" />
              <div className="pointer-events-none absolute right-36 -bottom-44 size-72 rounded-full bg-[#2db9ee]/10 blur-2xl" />
              <div className="relative max-w-2xl">
                <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-extrabold text-[#82e3ff]">
                  <Sparkles className="size-3.5" aria-hidden="true" />
                  NOWA PRZYGODA
                </span>
                <h2 className="mt-5 text-3xl leading-tight font-extrabold tracking-[-0.04em] sm:text-4xl">
                  Opowiedz nam o swoim idealnym dniu w mieście.
                </h2>
                <p className="mt-4 max-w-xl leading-7 text-[#bad0dc]">
                  Kilka pytań wystarczy, żeby stworzyć plan z mapą, przystankami, czasem i kosztami.
                </p>
                <Link
                  href="/planner"
                  className="group mt-8 inline-flex h-13 items-center justify-center gap-2 rounded-full bg-[#2db9ee] px-6 font-extrabold text-white shadow-[0_12px_28px_rgba(45,185,238,0.25)] transition hover:-translate-y-0.5 hover:bg-[#21a9dd] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-white/20"
                >
                  Stwórz nowy plan
                  <ArrowRight className="size-5 transition group-hover:translate-x-1" aria-hidden="true" />
                </Link>
              </div>
              <div className="relative mt-10 grid gap-3 sm:grid-cols-3">
                {facts.map(({ icon: Icon, label, value }) => (
                  <div key={label} className="flex items-center gap-3 rounded-2xl bg-white/[0.08] p-3.5 backdrop-blur">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 text-[#7edfff]">
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                    <div>
                      <p className="text-[10px] font-bold tracking-wide text-[#96b5c5] uppercase">{label}</p>
                      <p className="mt-0.5 text-xs font-bold text-white">{value}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <aside className="relative overflow-hidden rounded-[2.4rem] border border-white bg-white/85 p-7 shadow-[0_22px_55px_rgba(63,143,177,0.11)] backdrop-blur sm:p-8">
              <div className="absolute -top-14 -right-16 size-44 rounded-full bg-[#d9f5ff]" />
              <span className="relative flex size-12 items-center justify-center rounded-2xl bg-[#e2f7fe] text-[#18a4d8]">
                <Compass className="size-6" aria-hidden="true" />
              </span>
              <h2 className="relative mt-6 text-2xl font-extrabold tracking-[-0.035em]">Plan szyty na miarę</h2>
              <p className="relative mt-3 text-sm leading-7 text-[#668094]">
                Nie narzucamy gotowych rankingów. Pytamy o to, co naprawdę lubisz, i budujemy trasę wokół Ciebie.
              </p>
              <div className="relative mt-7 space-y-3">
                {["Twoje zainteresowania", "Twój budżet", "Twoje tempo"].map((item, index) => (
                  <div key={item} className="flex items-center gap-3 text-sm font-bold text-[#3c5c71]">
                    <span className="flex size-7 items-center justify-center rounded-full bg-[#e8f8fe] text-xs text-[#159dcc]">{index + 1}</span>
                    {item}
                  </div>
                ))}
              </div>
            </aside>
          </div>

          <section className="mt-20">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
              <div>
                <p className="text-xs font-extrabold tracking-[0.18em] text-[#159dcc] uppercase">Szybki start</p>
                <h2 className="mt-2 text-3xl font-extrabold tracking-[-0.04em]">Pomysły na Twój dzień</h2>
              </div>
              <p className="max-w-sm text-sm leading-6 text-[#7890a2]">Wybierz klimat, a w planerze dopracujesz szczegóły.</p>
            </div>

            <div className="mt-7 grid gap-5 lg:grid-cols-3">
              {quickPlans.map(({ icon: Icon, title, description, meta, color }) => (
                <Link
                  key={title}
                  href="/planner"
                  className="group rounded-[2rem] border border-white bg-white/90 p-6 shadow-[0_16px_45px_rgba(63,143,177,0.09)] transition hover:-translate-y-1 hover:shadow-[0_24px_55px_rgba(63,143,177,0.15)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#2db9ee]/20"
                >
                  <div className="flex items-start justify-between gap-4">
                    <span className={`flex size-12 items-center justify-center rounded-2xl ${color}`}>
                      <Icon className="size-5" aria-hidden="true" />
                    </span>
                    <span className="flex size-9 items-center justify-center rounded-full bg-[#f0f8fb] text-[#6f899c] transition group-hover:bg-[#2db9ee] group-hover:text-white">
                      <ArrowRight className="size-4 transition group-hover:translate-x-0.5" aria-hidden="true" />
                    </span>
                  </div>
                  <h3 className="mt-6 text-xl font-extrabold tracking-[-0.025em]">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#668094]">{description}</p>
                  <p className="mt-5 text-[11px] font-extrabold tracking-wide text-[#159dcc] uppercase">{meta}</p>
                </Link>
              ))}
            </div>
          </section>

          <section className="mt-20 overflow-hidden rounded-[2.2rem] border border-[#dcecf3] bg-white/70 p-7 sm:flex sm:items-center sm:justify-between sm:p-9">
            <div className="flex items-start gap-4">
              <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-[#e5f7fe] text-[#159dcc]">
                <Route className="size-5" aria-hidden="true" />
              </span>
              <div>
                <h2 className="text-lg font-extrabold">Nie masz jeszcze planu?</h2>
                <p className="mt-1 max-w-xl text-sm leading-6 text-[#668094]">
                  Każda dobra trasa zaczyna się od jednego pytania. Odpowiedz na nie i ruszaj.
                </p>
              </div>
            </div>
            <Link href="/planner" className="mt-5 inline-flex items-center gap-2 text-sm font-extrabold text-[#159dcc] transition hover:text-[#0d7eaa] sm:mt-0">
              Otwórz planer
              <Navigation className="size-4 fill-current" aria-hidden="true" />
            </Link>
          </section>
        </section>
      </div>

      <SiteFooter />
    </main>
  );
}
