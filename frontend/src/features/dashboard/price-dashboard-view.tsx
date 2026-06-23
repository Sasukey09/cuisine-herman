"use client";

import { useState } from "react";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  PiggyBank,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  ChefHat,
  LineChart,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  usePriceDashboard,
  useStoredPriceAlerts,
  useProductPriceHistory,
} from "@/hooks/use-purchasing";
import { useProducts } from "@/hooks/use-products";
import { formatCurrency } from "@/lib/utils";
import type { PriceMovement } from "@/services/types";

function PriceEvolutionChart() {
  const { data: products } = useProducts();
  const [picked, setPicked] = useState("");
  const selected = picked || products?.[0]?.id || "";
  const { data: history } = useProductPriceHistory(selected || undefined);

  const bars = (history?.purchases ?? [])
    .filter((p) => p.unit_cost_standard != null)
    .slice(-8);
  const max = Math.max(1, ...bars.map((b) => b.unit_cost_standard ?? 0));
  const unit = bars[bars.length - 1]?.unit_code ?? "u";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <LineChart className="h-4 w-4 text-primary" />
            Évolution du coût
          </CardTitle>
          <select
            value={selected}
            onChange={(e) => setPicked(e.target.value)}
            className="h-9 rounded-lg border border-input bg-card px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {(products ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <CardDescription>Coût standardisé par {unit} sur les derniers achats.</CardDescription>
      </CardHeader>
      <CardContent>
        {bars.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            Pas assez d&apos;achats pour ce produit.
          </p>
        ) : (
          <div className="flex h-[200px] items-end gap-3 px-1">
            {bars.map((b) => (
              <div key={b.id} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
                <span className="text-[11px] font-semibold text-foreground/80">
                  {formatCurrency(b.unit_cost_standard)}
                </span>
                <div
                  className="w-full max-w-[54px] rounded-t-md bg-primary"
                  style={{ height: `${Math.max(4, ((b.unit_cost_standard ?? 0) / max) * 100)}%` }}
                />
                <span className="text-[11px] text-muted-foreground">
                  {b.purchase_date ? b.purchase_date.slice(8, 10) + "/" + b.purchase_date.slice(5, 7) : "—"}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MovementRow({ m, up }: { m: PriceMovement; up: boolean }) {
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <Link
      href={`/produits/${m.product_id}`}
      className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-muted/60"
    >
      <span className="font-medium">{m.product_name ?? "Produit"}</span>
      <span className={`flex items-center gap-2 tabular-nums ${up ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`}>
        {formatCurrency(m.old_cost)} → {formatCurrency(m.new_cost)}
        <Badge variant={up ? "destructive" : "success"} className="gap-1">
          <Icon className="h-3 w-3" />
          {up ? "+" : ""}{m.change_pct.toFixed(1)}%
        </Badge>
      </span>
    </Link>
  );
}

export function PriceDashboardView() {
  const { data, isLoading } = usePriceDashboard();
  const { data: alerts } = useStoredPriceAlerts();

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  const d = data;
  const empty =
    !d || (d.most_increased.length === 0 && d.most_decreased.length === 0 && d.savings_opportunities.length === 0);

  return (
    <div className="space-y-4">
      <PriceEvolutionChart />

      {empty && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Pas encore assez de données. Importez au moins deux factures contenant les mêmes
            produits pour voir les variations de prix.
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4 text-red-500" /> Produits les plus augmentés
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {d && d.most_increased.length > 0 ? (
              d.most_increased.map((m) => <MovementRow key={m.product_id} m={m} up />)
            ) : (
              <p className="px-2 py-4 text-sm text-muted-foreground">Aucune hausse détectée.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingDown className="h-4 w-4 text-emerald-500" /> Produits les plus baissés
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {d && d.most_decreased.length > 0 ? (
              d.most_decreased.map((m) => <MovementRow key={m.product_id} m={m} up={false} />)
            ) : (
              <p className="px-2 py-4 text-sm text-muted-foreground">Aucune baisse détectée.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <PiggyBank className="h-4 w-4 text-emerald-600" /> Économies possibles
          </CardTitle>
          <CardDescription>
            En achetant chaque produit chez son fournisseur le moins cher
            {d ? ` · potentiel ${formatCurrency(d.potential_savings_total)}/unité cumulé` : ""}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {d && d.savings_opportunities.length > 0 ? (
            d.savings_opportunities.map((s) => (
              <div key={s.product_id} className="flex items-center justify-between px-2 py-1.5 text-sm">
                <Link href={`/produits/${s.product_id}`} className="font-medium hover:underline">
                  {s.product_name ?? "Produit"}
                </Link>
                <span className="text-muted-foreground">
                  {s.cheapest_supplier ?? "—"} à {formatCurrency(s.cheapest_cost)}/{s.unit_code ?? "u"}
                  <Badge variant="success" className="ml-2">−{s.saving_pct ?? 0}%</Badge>
                </span>
              </div>
            ))
          ) : (
            <p className="px-2 py-4 text-sm text-muted-foreground">
              Aucune opportunité (un seul fournisseur par produit pour l&apos;instant).
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ChefHat className="h-4 w-4" /> Impact sur les recettes
          </CardTitle>
          <CardDescription>Recettes dont le coût a augmenté suite à une hausse de prix.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {d && d.recipe_impact.length > 0 ? (
            d.recipe_impact.map((r, i) => (
              <div key={i} className="flex items-center gap-2 px-2 py-1.5 text-sm">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
                {r.recipe_id ? (
                  <Link href={`/recettes/${r.recipe_id}`} className="hover:underline">{r.message}</Link>
                ) : (
                  <span>{r.message}</span>
                )}
              </div>
            ))
          ) : (
            <p className="px-2 py-4 text-sm text-muted-foreground">Aucun impact recette détecté.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className="h-4 w-4 text-amber-500" /> Alertes de prix
          </CardTitle>
          <CardDescription>Variations détectées automatiquement à l&apos;import des factures.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {alerts && alerts.length > 0 ? (
            alerts.slice(0, 20).map((a) => (
              <div key={a.id} className="flex items-center gap-2 px-2 py-1.5 text-sm">
                {a.type === "price_decrease" ? (
                  <ArrowDownRight className="h-4 w-4 shrink-0 text-emerald-500" />
                ) : (
                  <ArrowUpRight className="h-4 w-4 shrink-0 text-red-500" />
                )}
                <span>{a.message}</span>
              </div>
            ))
          ) : (
            <p className="px-2 py-4 text-sm text-muted-foreground">Aucune alerte pour le moment.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
