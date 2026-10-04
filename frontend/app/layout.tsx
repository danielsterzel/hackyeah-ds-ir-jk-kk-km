import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono, Inter, Montserrat } from "next/font/google";

import { Providers } from "@/app/providers";
import { cn } from "@/lib/utils";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const montserrat = Montserrat({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "VentureFlux — Kraków w Twoim rytmie",
    template: "%s | VentureFlux",
  },
  description:
    "Osobisty planer zwiedzania Krakowa, dopasowany do Twojego czasu, budżetu i zainteresowań.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="pl"
      className={cn(
        "h-full antialiased",
        geistSans.variable,
        geistMono.variable,
        inter.variable,
        "font-sans",
      )}
    >
      <body className={`flex min-h-full flex-col ${montserrat.className}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
