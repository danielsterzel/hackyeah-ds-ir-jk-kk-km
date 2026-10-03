"use client";

import dynamic from "next/dynamic";

import type { Proposal } from "@/types/plan";

const TripMap = dynamic(
  () => import("@/components/map/TripMap").then((module) => module.TripMap),
  {
    ssr: false,
    loading: () => <div className="h-[460px] animate-pulse rounded-2xl bg-emerald-950/5 sm:h-[600px]" />,
  },
);

export function TripMapLoader({ proposal }: { proposal: Proposal }) {
  return <TripMap proposal={proposal} />;
}
