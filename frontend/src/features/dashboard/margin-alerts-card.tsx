"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

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
import type { MarginAlert } from "@/services/types";

export function MarginAlertsCard({
  alerts,
  loading,
}: {
  alerts: MarginAlert[];
  loading?: boolean;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          Alertes marges
        </CardTitle>
        <CardDescription>Recettes au food cost &gt; 35 %</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)
        ) : alerts.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
            <CheckCircle2 className="h-6 w-6 text-emerald-500" />
            Aucune recette en alerte. 🎉
          </div>
        ) : (
          alerts.map((a) => (
            <Link
              key={a.recipe_version_id}
              href={`/recettes/${a.recipe_id}`}
              className="flex items-center justify-between rounded-md border p-3 transition-colors hover:bg-accent"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{a.recipe_name ?? "Recette"}</p>
                <p className="text-xs text-muted-foreground">
                  Coût/portion {formatCurrency(a.cost_per_portion)}
                </p>
              </div>
              <Badge variant={(a.food_cost_pct ?? 0) > 45 ? "destructive" : "warning"}>
                {formatPercent(a.food_cost_pct)}
              </Badge>
            </Link>
          ))
        )}
      </CardContent>
    </Card>
  );
}
