"use client";

import Link from "next/link";
import { TrendingUp, CheckCircle2, ArrowUpRight } from "lucide-react";

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
import type { PriceAlert } from "@/services/types";

export function PriceAlertsCard({
  alerts,
  loading,
}: {
  alerts: PriceAlert[];
  loading?: boolean;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="h-4 w-4 text-primary" />
          Alertes prix
        </CardTitle>
        <CardDescription>Hausses de prix fournisseurs (&gt; 10 %)</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)
        ) : alerts.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
            <CheckCircle2 className="h-6 w-6 text-emerald-500" />
            Aucune hausse de prix détectée.
          </div>
        ) : (
          alerts.map((a) => (
            <Link
              key={a.product_id}
              href={`/produits`}
              className="flex items-center justify-between rounded-md border p-3 transition-colors hover:bg-accent"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{a.product_name ?? "Produit"}</p>
                <p className="text-xs text-muted-foreground">
                  {formatCurrency(a.previous_price, a.currency ?? "EUR")} →{" "}
                  {formatCurrency(a.latest_price, a.currency ?? "EUR")}
                </p>
              </div>
              <Badge variant={(a.change_pct ?? 0) > 25 ? "destructive" : "warning"}>
                <ArrowUpRight className="mr-0.5 h-3 w-3" />
                {formatPercent(a.change_pct)}
              </Badge>
            </Link>
          ))
        )}
      </CardContent>
    </Card>
  );
}
