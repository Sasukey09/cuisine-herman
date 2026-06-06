"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";
import type { TopProduct } from "@/services/types";

export function TopProductsCard({
  products,
  loading,
}: {
  products: TopProduct[];
  loading?: boolean;
}) {
  const max = Math.max(1, ...products.map((p) => p.total_spend));

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-base">Produits les plus achetés</CardTitle>
        <CardDescription>Par dépense cumulée</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)
        ) : products.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Aucun achat enregistré.
          </p>
        ) : (
          products.map((p) => (
            <div key={p.product_id} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="truncate font-medium">{p.name ?? "—"}</span>
                <span className="ml-2 shrink-0 tabular-nums text-muted-foreground">
                  {formatCurrency(p.total_spend)}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.max(4, (p.total_spend / max) * 100)}%` }}
                />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
