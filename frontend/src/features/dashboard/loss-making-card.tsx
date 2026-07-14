"use client";

import Link from "next/link";
import { CheckCircle2, CircleHelp, TrendingDown } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { LossReport } from "@/services/types";

/**
 * Dishes sold below what they cost to make.
 *
 * The platform has always computed this margin, and always stored it, and never
 * once compared it to zero. Which meant an endpoint alone would not have fixed
 * anything: a number nobody is shown is still a number nobody knows. Hence its
 * place at the top of the dashboard rather than at the bottom — "you are losing
 * money right now" is not a footnote.
 */
export function LossMakingCard({
  report,
  loading,
}: {
  report?: LossReport;
  loading?: boolean;
}) {
  const losing = report?.losing_money ?? [];
  const unknown = [...(report?.no_selling_price ?? []), ...(report?.not_costable ?? [])];

  return (
    <Card className={losing.length > 0 ? "border-destructive/50" : undefined}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingDown
            className={`h-4 w-4 ${losing.length > 0 ? "text-destructive" : "text-emerald-500"}`}
          />
          Plats vendus à perte
        </CardTitle>
        <CardDescription>
          {losing.length > 0
            ? `${formatCurrency(report?.loss_per_portion_total)} perdus à chaque tournée de ces plats`
            : "Coût d’une portion comparé à son prix de vente"}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-2">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)
        ) : (
          <>
            {losing.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-6 text-center text-sm text-muted-foreground">
                <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                Aucun plat vendu en dessous de son coût.
              </div>
            ) : (
              losing.map((dish) => (
                <Link
                  key={dish.recipe_id}
                  href={`/recettes/${dish.recipe_id}`}
                  className="flex items-center justify-between rounded-md border border-destructive/30 bg-destructive/5 p-3 transition-colors hover:bg-destructive/10"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{dish.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Coûte {formatCurrency(dish.cost_per_portion)} · vendu{" "}
                      {formatCurrency(dish.selling_price)}
                      {dish.food_cost_pct != null && ` · food cost ${formatPercent(dish.food_cost_pct)}`}
                    </p>
                  </div>
                  <Badge variant="destructive" className="shrink-0">
                    −{formatCurrency(dish.loss_per_portion)} / assiette
                  </Badge>
                </Link>
              ))
            )}

            {/* A dish you cannot evaluate is not a healthy dish. It is exactly
                where the loss hides, so it is named rather than left out. */}
            {unknown.length > 0 && (
              <div className="flex items-start gap-2 rounded-md border border-dashed p-3 text-xs text-muted-foreground">
                <CircleHelp className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  <strong className="font-medium text-foreground">
                    {unknown.length} plat{unknown.length > 1 ? "s" : ""}
                  </strong>{" "}
                  {unknown.length > 1 ? "ne peuvent" : "ne peut"} pas être évalué
                  {unknown.length > 1 ? "s" : ""} : prix de vente ou prix d’un ingrédient manquant.
                  Tant qu’{unknown.length > 1 ? "ils restent" : "il reste"} inconnu
                  {unknown.length > 1 ? "s" : ""}, une perte peut s’y cacher.
                </span>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
