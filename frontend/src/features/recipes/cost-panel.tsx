"use client";

import { useState } from "react";
import { Calculator, Loader2, AlertCircle } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useComputeCost } from "@/hooks/use-recipes";
import { formatCurrency, formatPercent } from "@/lib/utils";

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-xl font-semibold ${accent ?? ""}`}>{value}</p>
    </div>
  );
}

export function CostPanel({
  recipeId,
  versionId,
}: {
  recipeId: string;
  versionId: string;
}) {
  const compute = useComputeCost(recipeId, versionId);
  const [sellingPrice, setSellingPrice] = useState("");

  const run = () => {
    const price = sellingPrice ? Number(sellingPrice) : null;
    compute.mutate({ selling_price: price });
  };

  const result = compute.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Coût matière</CardTitle>
        <CardDescription>
          Calcule le coût à partir des derniers prix d&apos;achat connus.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="space-y-2 sm:max-w-xs">
            <Label htmlFor="selling_price">Prix de vente / portion (optionnel)</Label>
            <Input
              id="selling_price"
              type="number"
              step="any"
              placeholder="Pour food cost & marge"
              value={sellingPrice}
              onChange={(e) => setSellingPrice(e.target.value)}
            />
          </div>
          <Button onClick={run} disabled={compute.isPending}>
            {compute.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Calculator className="h-4 w-4" />
            )}
            Calculer
          </Button>
        </div>

        {result && (
          <>
            {result.has_missing_prices && (
              <div className="flex items-center gap-2 rounded-md bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
                <AlertCircle className="h-4 w-4" />
                Certains ingrédients n&apos;ont pas de prix connu : le coût est partiel.
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label="Coût matière total" value={formatCurrency(result.computed_cost_total)} />
              <Metric label="Coût / portion" value={formatCurrency(result.cost_per_portion)} />
              <Metric
                label="Food cost"
                value={formatPercent(result.food_cost_pct)}
                accent="text-amber-600 dark:text-amber-400"
              />
              <Metric
                label="Marge / portion"
                value={formatCurrency(result.margin_estimated)}
                accent={
                  (result.margin_estimated ?? 0) >= 0
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-destructive"
                }
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
