"use client";

import Link from "next/link";
import { Award, PackageCheck, Clock, TrendingUp, TrendingDown } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { useSupplierOverview } from "@/hooks/use-suppliers";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";

/** La fiche fournisseur 360°, en tête de page.
 *
 *  Un score n'est affiché que s'il a été calculé sur des faits — sinon on
 *  montre honnêtement « pas encore noté », pas un 0 trompeur. */
export function SupplierScorecard({ supplierId }: { supplierId: string }) {
  const { data } = useSupplierOverview(supplierId);
  if (!data) return null;

  const pct = (v?: number | null) => (v == null ? "—" : `${Math.round(v * 100)} %`);

  return (
    <div className="space-y-4">
      {/* Ligne de KPI : la dépense réelle et le score, ce qu'on regarde d'abord. */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          icon={<TrendingUp className="h-5 w-5 text-primary" />}
          value={formatCurrency(data.annual_amount)}
          label="Payé sur 12 mois"
        />
        <ScoreKpi score={data.score} basis={data.score_basis} />
        <Kpi
          icon={<PackageCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />}
          value={pct(data.conformity_rate)}
          label={`Conformité · ${data.receipt_count} réception(s)`}
        />
        <Kpi
          icon={<Clock className="h-5 w-5 text-amber-600 dark:text-amber-400" />}
          value={data.on_time_rate == null ? "—" : pct(data.on_time_rate)}
          label={`Ponctualité${data.late_count ? ` · ${data.late_count} retard(s)` : ""}`}
        />
      </div>

      {/* Volumes du cycle : devis → commandes → réceptions → factures. */}
      <Card>
        <CardContent className="flex flex-wrap gap-x-8 gap-y-2 py-4 text-sm">
          <Count n={data.quote_count} label="devis" />
          <Count n={data.order_count} label="commandes" />
          <Count n={data.receipt_count} label="réceptions" />
          <Count n={data.invoice_count} label="factures" />
          <Count n={data.distinct_products} label="produits" />
          {data.price_trend_pct != null ? (
            <span className="inline-flex items-center gap-1.5">
              {data.price_trend_pct > 0 ? (
                <TrendingUp className="h-4 w-4 text-red-600 dark:text-red-400" />
              ) : (
                <TrendingDown className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              )}
              <span
                className={cn(
                  "font-semibold tabular-nums",
                  data.price_trend_pct > 0
                    ? "text-red-600 dark:text-red-400"
                    : "text-emerald-600 dark:text-emerald-400",
                )}
              >
                {data.price_trend_pct > 0 ? "+" : ""}
                {formatNumber(data.price_trend_pct, 1)} %
              </span>
              <span className="text-muted-foreground">prix sur 1 an</span>
            </span>
          ) : null}
        </CardContent>
      </Card>

      {/* Économies : ce que la mise en concurrence a rapporté. Rien si aucune
          ligne n'a été comparée — on n'annonce pas une économie qu'on n'a pas. */}
      {(data.savings?.compared_lines ?? 0) > 0 ? (
        <Card>
          <CardContent className="py-4">
            <div className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
              Économies (12 mois) · {data.savings?.compared_lines} ligne(s) comparée(s)
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <div className="text-lg font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                  {formatCurrency(data.savings?.realized)}
                </div>
                <div className="text-xs text-muted-foreground">{data.savings?.labels.realized}</div>
              </div>
              <div>
                <div className="text-lg font-bold tabular-nums text-amber-600 dark:text-amber-400">
                  {formatCurrency(data.savings?.missed)}
                </div>
                <div className="text-xs text-muted-foreground">{data.savings?.labels.missed}</div>
              </div>
              <div>
                <div className="text-lg font-bold tabular-nums">
                  {data.savings?.best_choice_rate == null
                    ? "—"
                    : `${Math.round(data.savings.best_choice_rate * 100)} %`}
                </div>
                <div className="text-xs text-muted-foreground">
                  {data.savings?.labels.best_choice_rate}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Évolution mensuelle : barres simples, pas de librairie pour 12 points. */}
      {data.monthly.length > 1 ? <MonthlyBars monthly={data.monthly} /> : null}

      {data.top_products.length > 0 ? (
        <Card>
          <CardContent className="py-4">
            <div className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
              Produits les plus achetés
            </div>
            <ul className="space-y-1.5">
              {data.top_products.slice(0, 6).map((p) => (
                <li key={p.product_id} className="flex items-center justify-between gap-3 text-sm">
                  <Link href={`/produits/${p.product_id}`} className="truncate hover:underline">
                    {p.product_name ?? "Produit"}
                  </Link>
                  <span className="tabular-nums font-medium">{formatCurrency(p.amount)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function Kpi({ icon, value, label }: { icon: React.ReactNode; value: string; label: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4">
        {icon}
        <div className="min-w-0">
          <div className="truncate text-lg font-bold tabular-nums">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function ScoreKpi({
  score,
  basis,
}: {
  score?: number | null;
  basis: { receipts_judged: number };
}) {
  const tone =
    score == null
      ? "text-muted-foreground"
      : score >= 80
        ? "text-emerald-600 dark:text-emerald-400"
        : score >= 50
          ? "text-amber-600 dark:text-amber-400"
          : "text-red-600 dark:text-red-400";
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4">
        <Award className={cn("h-5 w-5", tone)} />
        <div className="min-w-0">
          <div className={cn("text-lg font-bold tabular-nums", tone)}>
            {score == null ? "—" : `${score}/100`}
          </div>
          <div className="text-xs text-muted-foreground">
            {score == null
              ? "Pas encore noté"
              : `Score fournisseur · ${basis.receipts_judged} réception(s)`}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Count({ n, label }: { n: number; label: string }) {
  return (
    <span>
      <span className="font-semibold tabular-nums">{n}</span>{" "}
      <span className="text-muted-foreground">{label}</span>
    </span>
  );
}

function MonthlyBars({ monthly }: { monthly: Array<{ month: string; amount: number }> }) {
  const max = Math.max(...monthly.map((m) => m.amount), 1);
  return (
    <Card>
      <CardContent className="py-4">
        <div className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
          Dépense mensuelle
        </div>
        <div className="flex items-end gap-1.5" style={{ height: 96 }}>
          {monthly.map((m) => (
            <div key={m.month} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-primary/70"
                style={{ height: `${Math.max((m.amount / max) * 76, 2)}px` }}
                title={`${m.month} · ${formatCurrency(m.amount)}`}
              />
              <span className="text-[9px] text-muted-foreground">{m.month.slice(5)}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
