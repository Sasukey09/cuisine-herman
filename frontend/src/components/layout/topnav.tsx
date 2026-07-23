"use client";

import { useState } from "react";
import { Menu, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth-store";

export function Topnav({ onMenu }: { onMenu: () => void }) {
  const router = useRouter();
  const [term, setTerm] = useState("");
  // Read-only accounts were shown "+ Importer une facture", which leads to an
  // upload dialog they are not allowed to open: a dead end.
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = term.trim();
    if (q) router.push(`/produits?q=${encodeURIComponent(q)}`);
  };

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

      {/* Was a styled <div> that looked like a search box and did nothing. */}
      <form onSubmit={submit} className="hidden sm:block">
        <label htmlFor="global-search" className="sr-only">
          Rechercher un produit
        </label>
        <div className="flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm focus-within:border-primary sm:w-[220px]">
          <Search className="h-[15px] w-[15px] flex-none text-muted-foreground" />
          <input
            id="global-search"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Rechercher un produit…"
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
      </form>

      {canWrite && (
        // `?import=1` : la page Factures ouvre directement le dialogue d'import.
        // Avant, ce bouton pointait sur "/factures" tout court : si on y était
        // déjà, cliquer ne faisait RIEN de visible (l'utilisateur croyait le
        // bouton mort). Il déclenche maintenant l'import où qu'on soit.
        <Button asChild className="rounded-full">
          <Link href="/factures?import=1">+ Importer une facture</Link>
        </Button>
      )}
    </header>
  );
}
