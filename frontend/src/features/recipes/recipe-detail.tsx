"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ClipboardList, Plus, ChefHat } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ListOrdered } from "lucide-react";

import { VersionFormDialog } from "./version-form-dialog";
import { CostPanel } from "./cost-panel";
import { useRecipe, useRecipeVersion, useRecipeInstructions } from "@/hooks/use-recipes";
import { useProducts } from "@/hooks/use-products";
import { useAuthStore } from "@/stores/auth-store";
import { formatNumber, formatPercent } from "@/lib/utils";

export function RecipeDetail({ recipeId }: { recipeId: string }) {
  const { data: recipe, isLoading, isError } = useRecipe(recipeId);
  const version = useRecipeVersion(recipeId, recipe?.current_version_id ?? null);
  const { data: instructions } = useRecipeInstructions(recipeId);
  const { data: products } = useProducts();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));
  const [versionOpen, setVersionOpen] = useState(false);

  const productNames = useMemo(() => {
    const m = new Map<string, string>();
    products?.forEach((p) => m.set(p.id, p.name));
    return m;
  }, [products]);

  // Current ingredients, in the shape the editor expects — so opening it shows
  // what's already there and the user adds/edits/removes on top of it. Declared
  // before any early return so the hook order stays stable.
  const initialIngredients = useMemo(
    () =>
      (version.data?.ingredients ?? []).map((i) => ({
        product_id: i.product_id ?? "",
        qty: i.qty ?? undefined,
        loss_pct: i.loss_pct ?? 0,
        yield_pct: i.yield_pct ?? 100,
      })),
    [version.data],
  );

  if (isError) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Recette introuvable.
          <div className="mt-4">
            <Button asChild variant="outline">
              <Link href="/recettes">Retour aux recettes</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const hasVersion = Boolean(recipe?.current_version_id);

  return (
    <div className="space-y-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
        <Link href="/recettes">
          <ArrowLeft className="h-4 w-4" />
          Recettes
        </Link>
      </Button>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            {isLoading || !recipe ? (
              <Skeleton className="h-7 w-48" />
            ) : (
              <>
                <CardTitle>{recipe.name}</CardTitle>
                <CardDescription>
                  {formatNumber(recipe.yield_qty)} portion(s)
                  {version.data ? ` · version ${version.data.version_number}` : ""}
                </CardDescription>
              </>
            )}
          </div>
          {canWrite && (
            <Button variant="outline" size="sm" onClick={() => setVersionOpen(true)}>
              <Plus className="h-4 w-4" />
              {hasVersion ? "Modifier les ingrédients" : "Ajouter les ingrédients"}
            </Button>
          )}
        </CardHeader>
      </Card>

      {/* Fiche technique */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ClipboardList className="h-4 w-4" />
            Fiche technique
          </CardTitle>
          <CardDescription>Ingrédients de la version courante.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {!hasVersion ? (
            <div className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground">
              <ChefHat className="h-8 w-8" />
              Aucune fiche technique. {canWrite ? "Ajoutez les ingrédients." : ""}
            </div>
          ) : version.isLoading || !version.data ? (
            <div className="space-y-2 px-6">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Ingrédient</TableHead>
                  <TableHead>Quantité</TableHead>
                  <TableHead>Perte</TableHead>
                  <TableHead className="pr-6">Rendement</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {version.data.ingredients.map((ing) => (
                  <TableRow key={ing.id ?? ing.product_id ?? ing.ingredient_name}>
                    <TableCell className="pl-6 font-medium">
                      {(ing.product_id ? productNames.get(ing.product_id) : null) ??
                        ing.ingredient_name ??
                        "Produit"}
                    </TableCell>
                    <TableCell className="tabular-nums">{formatNumber(ing.qty)}</TableCell>
                    <TableCell className="text-muted-foreground">{formatPercent(ing.loss_pct)}</TableCell>
                    <TableCell className="pr-6 text-muted-foreground">{formatPercent(ing.yield_pct)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Procédure */}
      {instructions && instructions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ListOrdered className="h-4 w-4" />
              Procédure
            </CardTitle>
            <CardDescription>Étapes de préparation.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal space-y-2 pl-5 text-sm">
              {instructions.map((s) => (
                <li key={s.step_number}>{s.content}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* Coûts */}
      {hasVersion && recipe?.current_version_id && (
        <CostPanel
          recipeId={recipeId}
          versionId={recipe.current_version_id}
          sellingPrice={recipe.selling_price}
        />
      )}

      <VersionFormDialog
        open={versionOpen}
        onOpenChange={setVersionOpen}
        recipeId={recipeId}
        initialIngredients={initialIngredients}
      />
    </div>
  );
}
