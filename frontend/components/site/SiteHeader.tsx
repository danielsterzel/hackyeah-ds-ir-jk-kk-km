import Link from "next/link";
import { ArrowRight, Navigation } from "lucide-react";

import { cn } from "@/lib/utils";

type SiteHeaderProps = {
  active?: "landing" | "home" | "planner";
};

export function SiteHeader({ active = "landing" }: SiteHeaderProps) {
  const navItem =
    "rounded-full px-4 py-2 text-sm font-bold transition hover:bg-white hover:text-[#17364d]";

  return (
    <header className="relative z-30 mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-10">
      <Link
        href="/"
        className="flex items-center gap-3 rounded-2xl outline-none focus-visible:ring-4 focus-visible:ring-[#31b9ed]/20"
        aria-label="VentureFlux — strona startowa"
      >
        <span className="flex size-11 items-center justify-center rounded-2xl bg-[#2db9ee] text-white shadow-[0_8px_24px_rgba(45,185,238,0.3)]">
          <Navigation className="size-5 fill-current" aria-hidden="true" />
        </span>
        <span>
          <span className="block text-lg font-extrabold tracking-[-0.04em] text-[#17364d]">
            VentureFlux
          </span>
          <span className="block text-[11px] font-semibold text-[#668094]">
            Twój miejski kompan
          </span>
        </span>
      </Link>

      <div className="flex items-center gap-2">
        <nav
          className="hidden items-center gap-1 text-[#668094] md:flex"
          aria-label="Główna nawigacja"
        >
          <Link
            href="/"
            aria-current={active === "landing" ? "page" : undefined}
            className={cn(
              navItem,
              active === "landing" && "bg-white text-[#17364d] shadow-sm",
            )}
          >
            O aplikacji
          </Link>
          <Link
            href="/home"
            aria-current={active === "home" ? "page" : undefined}
            className={cn(
              navItem,
              active === "home" && "bg-white text-[#17364d] shadow-sm",
            )}
          >
            Home
          </Link>
        </nav>

        <Link
          href="/planner"
          aria-current={active === "planner" ? "page" : undefined}
          className="group inline-flex h-11 items-center justify-center gap-2 rounded-full bg-[#17364d] px-4 text-sm font-bold text-white shadow-[0_10px_25px_rgba(23,54,77,0.18)] transition hover:-translate-y-0.5 hover:bg-[#244b65] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#31b9ed]/25 sm:px-5"
        >
          <span className="hidden sm:inline">Zaplanuj trasę</span>
          <span className="sm:hidden">Planer</span>
          <ArrowRight className="size-4 transition group-hover:translate-x-0.5" aria-hidden="true" />
        </Link>
      </div>
    </header>
  );
}
