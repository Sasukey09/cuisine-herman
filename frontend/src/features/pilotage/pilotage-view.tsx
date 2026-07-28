"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  PiggyBank,
  TrendingDown,
  TrendingUp,
  Target,
  Sparkles,
  ShoppingCart,
  PackageCheck,
  FileText,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
  Award,
  Clock,
  ShieldCheck,
} from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { SafeBoundary } from "@/components/safe-boundary";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/features/dashboard/stat-card";
import { usePurchasingKpi } from "@/hooks/use-purchasing-kpi";
import { formatCurrency, formatNumber } from "@/lib/utils";
import type { PurchasingKpi } from "@/services/types";

/** `best_choice_rate` / `conformity_rate` sont des fractions 0..1, nullable
 *  tant qu'il n'y a rien à comparer — on affiche « — » plutôt que 0 %. */
function pct(rate: number | null | undefined) {
  return rate == null ? "—" : `${Math.round(rate * 100)} %`;
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-2 mt-6 font-serif text-lg font-semibold">{children}</h2>;
}

function CycleGapsCard({
  cycle,
  labels,
}: {
  cycle: PurchasingKpi["cycle"];
  labels: Record<string, string>;
}) {
  return (
    <Card>
      <CardContent className="space-y-2 p-6 text-sm">
        <p className="mb-1 text-sm font-medium text-muted-foreground">Écarts du cycle</p>
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">
            {labels.gap_ordered_received ?? "Écart commandé → reçu"}
          </span>
          <span className="font-medium tabular-nums">{formatCurrency(cycle.gap_ordered_received)}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">
            {labels.gap_billed_received ?? "Écart facturé → reçu"}
          </span>
          <span className="font-medium tabular-nums">{formatCurrency(cycle.gap_billed_received)}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">{labels.missing_value ?? "En attente de livraison"}</span>
          <span className="font-medium tabular-nums">{formatCurrency(cycle.missing_value)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function PriceSummaryCard({ price }: { price: PurchasingKpi["price"] }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <div>
          <CardTitle className="text-base">Prix</CardTitle>
          <CardDescription>Variations détectées sur la fenêtre.</CardDescription>
        </div>
        <Link
          href="/prix"
          className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          Voir le détail <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <span className="flex items-center gap-1.5">
          <ArrowUpRight className="h-4 w-4 text-red-500" />
          <strong className="tabular-nums">{formatNumber(price.n_hausse, 0)}</strong> en hausse
        </span>
        <span className="flex items-center gap-1.5">
          <ArrowDownRight className="h-4 w-4 text-emerald-500" />
          <strong className="tabular-nums">{formatNumber(price.n_baisse, 0)}</strong> en baisse
        </span>
        <span className="flex items-center gap-1.5">
          <TrendingUp className="h-4 w-4 text-amber-500" />
          Pic :{" "}
          {price.top_inflation_pct == null ? "—" : `+${formatNumber(price.top_inflation_pct, 1)} %`}
        </span>
        <span className="flex items-center gap-1.5">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <strong className="tabular-nums">{formatNumber(price.n_critiques, 0)}</strong> critiques
        </span>
        <span className="flex items-center gap-1.5">
          <PiggyBank className="h-4 w-4 text-emerald-600" />
          {formatCurrency(price.switch_savings_total)} en changeant de fournisseur
        </span>
      </CardContent>
    </Card>
  );
}

function SupplierListCard<T extends { supplier_id: string; name: string }>({
  title,
  icon: Icon,
  items,
  empty,
  renderValue,
}: {
  title: string;
  icon: LucideIcon;
  items: T[];
  empty: string;
  renderValue: (item: T) => ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="h-4 w-4 text-primary" /> {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {items.length > 0 ? (
          items.map((item) => (
            <div key={item.supplier_id} className="flex items-center justify-between px-2 py-1.5 text-sm">
              <span className="truncate font-medium">{item.name}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">{renderValue(item)}</span>
            </div>
          ))
        ) : (
          <p className="px-2 py-4 text-sm text-muted-foreground">{empty}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function PilotageView() {
  const { data, isLoading, isError, error, refetch, isFetching } = usePurchasingKpi();

  if (isError) {
    return (
      <>
        <PageHeader
          title="Pilotage Achats"
          description="Vue d'ensemble du cycle achats : économies, commande-réception-facture, prix et fournisseurs."
        />
        <div className="rounded-xl border bg-card">
          <ErrorState error={error} onRetry={() => refetch()} retrying={isFetching} />
        </div>
      </>
    );
  }

  if (isLoading || !data) {
    return (
      <>
        <PageHeader
          title="Pilotage Achats"
          description="Vue d'ensemble du cycle achats : économies, commande-réception-facture, prix et fournisseurs."
        />
        <Skeleton className="h-64 w-full" />
      </>
    );
  }

  const { savings, cycle, price, suppliers, labels } = data;

  return (
    <>
      <PageHeader
        title={`Pilotage Achats · ${data.window_months} mois`}
        description="Vue d'ensemble du cycle achats : économies, commande-réception-facture, prix et fournisseurs."
      />

      <SectionTitle>Économies</SectionTitle>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title={savings.labels.realized}
          value={formatCurrency(savings.realized)}
          icon={PiggyBank}
          hint={`${formatNumber(savings.compared_lines, 0)} ligne(s) comparée(s)`}
          accentClassName="bg-gradient-teal text-white"
        />
        <StatCard
          title={savings.labels.missed}
          value={formatCurrency(savings.missed)}
          icon={TrendingDown}
          accentClassName="bg-gradient-danger text-white"
        />
        <StatCard
          title={savings.labels.best_choice_rate}
          value={pct(savings.best_choice_rate)}
          icon={Target}
          accentClassName="bg-gradient-amber text-white"
        />
        <StatCard
          title={labels.possible_open ?? "Économies possibles (devis ouverts)"}
          value={formatCurrency(data.possible_open)}
          icon={Sparkles}
          accentClassName="bg-gradient-brand text-white"
        />
      </div>

      <SectionTitle>Cycle achats</SectionTitle>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title={labels.ordered_total ?? "Commandé"}
          value={formatCurrency(cycle.ordered_total)}
          icon={ShoppingCart}
        />
        <StatCard
          title={labels.received_value ?? "Reçu"}
          value={formatCurrency(cycle.received_value)}
          icon={PackageCheck}
        />
        <StatCard
          title={labels.billed_total ?? "Facturé"}
          value={formatCurrency(cycle.billed_total)}
          icon={FileText}
        />
        <SafeBoundary>
          <CycleGapsCard cycle={cycle} labels={labels} />
        </SafeBoundary>
      </div>

      <SectionTitle>Prix</SectionTitle>
      <SafeBoundary>
        <PriceSummaryCard price={price} />
      </SafeBoundary>

      <SectionTitle>Fournisseurs</SectionTitle>
      <div className="grid gap-4 lg:grid-cols-3">
        <SafeBoundary>
          <SupplierListCard
            title={labels.most_competitive ?? "Plus compétitifs"}
            icon={Award}
            items={suppliers.most_competitive}
            empty="Pas encore assez de données."
            renderValue={(s) => formatCurrency(s.realized)}
          />
        </SafeBoundary>
        <SafeBoundary>
          <SupplierListCard
            title={labels.most_late ?? "En retard"}
            icon={Clock}
            items={suppliers.most_late}
            empty="Aucun retard détecté."
            renderValue={(s) => `${formatNumber(s.late_count, 0)} livraison(s)`}
          />
        </SafeBoundary>
        <SafeBoundary>
          <SupplierListCard
            title={labels.best_conformity ?? "Meilleure conformité"}
            icon={ShieldCheck}
            items={suppliers.best_conformity}
            empty="Pas encore assez de données."
            renderValue={(s) => pct(s.conformity_rate)}
          />
        </SafeBoundary>
      </div>
    </>
  );
}
