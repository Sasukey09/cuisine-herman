"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, ChefHat, Pencil, Trash2, FileUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { RecipeFormDialog } from "./recipe-form-dialog";
import { useEnrichedRecipes, useDeleteRecipe } from "@/hooks/use-recipes";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/utils";
import type { Recipe, RecipeRow } from "@/services/types";

export function RecipesView() {
  const { data: recipes, isLoading } = useEnrichedRecipes();
  const del = useDeleteRecipe();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Recipe | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RecipeRow | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[13.5px] text-muted-foreground">
          {recipes ? `${recipes.length} recette(s)` : " "}
        </div>
        {canWrite && (
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link href="/import-recette">
                <FileUp className="h-4 w-4" />
                Importer une recette PDF
              </Link>
            </Button>
            <Button variant="gradient" onClick={() => { setEditing(null); setFormOpen(true); }}>
              <Plus className="h-4 w-4" />
              Nouvelle recette
            </Button>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[230px] rounded-xl" />
          ))}
        </div>
      ) : !recipes || recipes.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border bg-card py-14 text-center text-sm text-muted-foreground">
          <ChefHat className="h-8 w-8" />
          Aucune recette pour le moment.
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {recipes.map((r) => {
            const fc =
              r.cost_per_portion != null && r.selling_price != null && r.selling_price > 0
                ? (r.cost_per_portion / r.selling_price) * 100
                : null;
            const fcColor =
              fc == null ? "#8a847a" : fc >= 33 ? "#b23a2e" : fc >= 25 ? "#e0983f" : "#059669";
            return (
            <div key={r.id} className="overflow-hidden rounded-xl border bg-card">
              <Link
                href={`/recettes/${r.id}`}
                className="flex h-24 items-center justify-center bg-secondary text-primary"
              >
                <ChefHat className="h-9 w-9" />
              </Link>
              <div className="p-[15px_17px]">
                <div className="flex items-center justify-between gap-2">
                  <Link href={`/recettes/${r.id}`} className="truncate font-serif text-[17px] font-semibold hover:underline">
                    {r.name}
                  </Link>
                  <Badge variant={r.defined ? "success" : "secondary"} className="flex-none">
                    {r.defined ? "Définie" : "À compléter"}
                  </Badge>
                </div>
                <div className="mt-1 text-[12.5px] text-muted-foreground">
                  {formatNumber(r.yield_qty)} portions
                  {r.cost_per_portion != null && ` · coût ${formatCurrency(r.cost_per_portion)}/portion`}
                </div>

                {fc != null && (
                  <div className="mt-3">
                    <div className="mb-1 flex items-center justify-between text-[11px]">
                      <span className="text-muted-foreground">Food cost</span>
                      <span className="font-semibold" style={{ color: fcColor }}>
                        {Math.round(fc)}%
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-[#e9dfca]">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${Math.min(100, fc)}%`, background: fcColor }}
                      />
                    </div>
                  </div>
                )}

                <div className="mt-3 flex items-center justify-between border-t pt-3">
                  <div>
                    <div className="text-[11px] text-muted-foreground">Prix de vente</div>
                    <div className="text-sm font-semibold">
                      {r.selling_price != null ? formatCurrency(r.selling_price) : "—"}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[11px] text-muted-foreground">Marge brute</div>
                    <div className="text-sm font-semibold text-[#5c7a4a]">
                      {r.margin_pct != null ? formatPercent(r.margin_pct) : "—"}
                    </div>
                  </div>
                </div>

                {canWrite && (
                  <div className="mt-3 flex items-center justify-between border-t pt-3">
                    <Link href={`/recettes/${r.id}`} className="text-[12.5px] font-semibold text-primary hover:underline">
                      Voir la fiche →
                    </Link>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Modifier"
                        onClick={() => {
                          setEditing({ id: r.id, name: r.name, yield_qty: r.yield_qty, selling_price: r.selling_price });
                          setFormOpen(true);
                        }}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" aria-label="Supprimer"
                        onClick={() => setDeleteTarget(r)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
            );
          })}
        </div>
      )}

      <RecipeFormDialog open={formOpen} onOpenChange={setFormOpen} recipe={editing} />

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette recette ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {deleteTarget?.name} » et sa fiche technique seront supprimées. Cette action est
              irréversible.
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
