import type { Metadata } from "next";
import { Public_Sans, Newsreader } from "next/font/google";
import "./globals.css";

import { Providers } from "@/components/providers";

const sans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});
const serif = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cuisine Herman — Gestion de coûts",
  description:
    "Plateforme SaaS de gestion des achats, factures, recettes et coûts matière.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={`${sans.variable} ${serif.variable} font-sans`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
