"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Search, Pencil, Trash2, Truck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { SupplierFormDialog } from "./supplier-form-dialog";
import { useEnrichedSuppliers, useDeleteSupplier } from "@/hooks/use-suppliers";
import { useDebounce } from "@/hooks/use-debounce";
import { useAuthStore } from "@/stores/auth-store";
import type { Supplier, SupplierRow } from "@/services/types";

export function SuppliersView() {
  const [search, setSearch] = useState("");
  const debounced = useDebounce(search, 300);
  const { data: suppliers, isLoading } = useEnrichedSuppliers(debounced || undefined);
  const del = useDeleteSupplier();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SupplierRow | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Rechercher un fournisseur…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {canWrite && (
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            Nouveau fournisseur
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[150px] rounded-xl" />
          ))}
        </div>
      ) : !suppliers || suppliers.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border bg-card py-14 text-center text-sm text-muted-foreground">
          <Truck className="h-8 w-8" />
          {debounced ? "Aucun fournisseur ne correspond." : "Aucun fournisseur pour le moment."}
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
          {suppliers.map((s) => (
            <div key={s.id} className="rounded-xl border bg-card p-[18px]">
              <div className="mb-2.5 flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-10 w-10 flex-none items-center justify-center rounded-[10px] bg-secondary font-serif text-lg font-semibold text-primary">
                    {(s.name || "?").slice(0, 1).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <Link href={`/fournisseurs/${s.id}`} className="block truncate text-[15px] font-semibold hover:underline">
                      {s.name}
                    </Link>
                    <div className="truncate text-xs text-muted-foreground">{s.code || "Fournisseur"}</div>
                  </div>
                </div>
                {canWrite && (
                  <div className="flex flex-none gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Modifier"
                      onClick={() => { setEditing(s); setFormOpen(true); }}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" aria-label="Supprimer"
                      onClick={() => setDeleteTarget(s)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </div>
              <div className="mb-3 truncate text-[12.5px] text-muted-foreground">
                {s.contact?.email || s.contact?.phone || "Aucun contact renseigné"}
              </div>
              <div className="flex items-center justify-between border-t pt-2.5">
                <span className="text-[12.5px]">
                  <b>{s.product_count}</b>{" "}
                  <span className="text-muted-foreground">produit{s.product_count > 1 ? "s" : ""}</span>
                </span>
                <Link href={`/fournisseurs/${s.id}`} className="text-[12.5px] font-semibold text-primary hover:underline">
                  Voir le catalogue →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      <SupplierFormDialog open={formOpen} onOpenChange={setFormOpen} supplier={editing} />

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce fournisseur ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {deleteTarget?.name} » sera supprimé. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget)
                  del.mutate(deleteTarget.id, { onSettled: () => setDeleteTarget(null) });
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
