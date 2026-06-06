"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, ChefHat } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RecipeFormDialog } from "./recipe-form-dialog";
import { useRecipes } from "@/hooks/use-recipes";
import { useAuthStore } from "@/stores/auth-store";
import { formatNumber } from "@/lib/utils";

export function RecipesView() {
  const { data: recipes, isLoading } = useRecipes();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        {canWrite && (
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            Nouvelle recette
          </Button>
        )}
      </div>

      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead>Portions</TableHead>
              <TableHead>Fiche technique</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                </TableRow>
              ))
            ) : !recipes || recipes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3}>
                  <div className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground">
                    <ChefHat className="h-8 w-8" />
                    Aucune recette pour le moment.
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              recipes.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">
                    <Link href={`/recettes/${r.id}`} className="hover:underline">
                      {r.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatNumber(r.yield_qty)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {r.current_version_id ? "Définie" : "À compléter"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <RecipeFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
