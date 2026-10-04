import Link from "next/link";
import { Navigation } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="relative z-10 border-t border-[#dceef6] bg-white/60">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-7 text-sm text-[#668094] sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-10">
        <Link href="/" className="flex items-center gap-2 font-extrabold text-[#17364d]">
          <span className="flex size-8 items-center justify-center rounded-xl bg-[#2db9ee] text-white">
            <Navigation className="size-4 fill-current" aria-hidden="true" />
          </span>
          VentureFlux
        </Link>
        <p>Twój dzień w Krakowie, ułożony po Twojemu.</p>
        <div className="flex gap-5 font-semibold">
          <Link className="transition hover:text-[#17364d]" href="/home">
            Home
          </Link>
          <Link className="transition hover:text-[#17364d]" href="/planner">
            Planer
          </Link>
        </div>
      </div>
    </footer>
  );
}
