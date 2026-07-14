"use client";

import { useMemo } from "react";
import { Wallet, Percent, ShoppingCart, TrendingDown } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/features/dashboard/stat-card";
import { CostTrendChart } from "@/features/dashboard/cost-trend-chart";
import { TopProductsCard } from "@/features/dashboard/top-products-card";
import { MarginAlertsCard } from "@/features/dashboard/margin-alerts-card";
import { PriceAlertsCard } from "@/features/dashboard/price-alerts-card";
import { LossMakingCard } from "@/features/dashboard/loss-making-card";
import {
  useCostTrends,
  useTopProducts,
  useMarginAlerts,
  usePriceAlerts,
  useLossMaking,
} from "@/hooks/use-dashboard";
import {
  aggregateByDay,
  average,
  latestPerVersion,
} from "@/features/dashboard/utils";
import { formatCurrency, formatPercent } from "@/lib/utils";

export default function DashboardPage() {
  const costTrends = useCostTrends();
  const topProducts = useTopProducts({ limit: 100 });
  const marginAlerts = useMarginAlerts(35);
  const priceAlerts = usePriceAlerts(10);
  const lossMaking = useLossMaking();

  // `?? []` crée un tableau neuf à chaque rendu : les useMemo qui en dépendent
  // se recalculaient donc à chaque fois, ce qui annule leur seule raison d'être.
  const points = useMemo(() => costTrends.data ?? [], [costTrends.data]);
  const products = topProducts.data ?? [];
  const alerts = marginAlerts.data ?? [];

  const daily = useMemo(() => aggregateByDay(points), [points]);
  const latest = useMemo(() => latestPerVersion(points), [points]);

  const avgCostPerPortion = average(latest.map((p) => p.cost_per_portion));
  const avgFoodCost = average(latest.map((p) => p.food_cost_pct));
  const totalSpend = products.reduce((sum, p) => sum + (p.total_spend ?? 0), 0);
  const losing = lossMaking.data?.losing_money ?? [];

  return (
    <>
      <PageHeader
        title="Tableau de bord"
        description="Vue d'ensemble de vos coûts matière et de vos achats."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Coût matière moyen / portion"
          value={formatCurrency(avgCostPerPortion)}
          icon={Wallet}
          loading={costTrends.isLoading}
          hint={`${latest.length} recette(s) calculée(s)`}
        />
        <StatCard
          title="Food cost moyen"
          value={formatPercent(avgFoodCost)}
          icon={Percent}
          loading={costTrends.isLoading}
          accentClassName="bg-amber-500/10 text-amber-600 dark:text-amber-400"
        />
        <StatCard
          title="Dépense cumulée"
          value={formatCurrency(totalSpend)}
          icon={ShoppingCart}
          loading={topProducts.isLoading}
          hint={`${products.length} produit(s) acheté(s)`}
          accentClassName="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
        />
        <StatCard
          title="Plats à perte"
          value={String(losing.length)}
          icon={TrendingDown}
          loading={lossMaking.isLoading}
          hint={
            losing.length > 0
              ? `${formatCurrency(lossMaking.data?.loss_per_portion_total)} perdus par tournée`
              : "Aucun plat sous son coût"
          }
          accentClassName={
            losing.length > 0
              ? "bg-destructive/10 text-destructive"
              : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
          }
        />
      </div>

      <div className="mt-4">
        <LossMakingCard report={lossMaking.data} loading={lossMaking.isLoading} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <CostTrendChart data={daily} loading={costTrends.isLoading} />
        </div>
        <MarginAlertsCard alerts={alerts} loading={marginAlerts.isLoading} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <TopProductsCard products={products.slice(0, 8)} loading={topProducts.isLoading} />
        <PriceAlertsCard alerts={priceAlerts.data ?? []} loading={priceAlerts.isLoading} />
      </div>
    </>
  );
}
