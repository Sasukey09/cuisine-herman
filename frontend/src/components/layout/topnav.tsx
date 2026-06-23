"use client";

import { Menu, Search } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function Topnav({ onMenu }: { onMenu: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur md:px-7">
      <Button
        variant="outline"
        size="icon"
        className="md:hidden"
        aria-label="Ouvrir le menu"
        onClick={onMenu}
      >
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex-1" />

      {/* Search pill (mockup) */}
      <div className="hidden items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm text-muted-foreground sm:flex sm:w-[200px]">
        <Search className="h-[15px] w-[15px] flex-none" />
        Rechercher…
      </div>

      {/* Primary action (mockup) */}
      <Button asChild className="rounded-full">
        <Link href="/factures">+ Importer une facture</Link>
      </Button>
    </header>
  );
}
