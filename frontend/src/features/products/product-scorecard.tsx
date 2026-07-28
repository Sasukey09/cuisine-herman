"use client";

import Link from "next/link";
import { Trophy, TrendingUp, TrendingDown, PiggyBank } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SafeBoundary } from "@/components/safe-boundary";
import { useProductOverview } from "@/hooks/use-products";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";

/** La fiche produit 360°, en tête de l'onglet « Vue d'ensemble ».
 *
 *  Miroir de `SupplierScorecard` côté produit : au lieu de juger un
 *  fournisseur, on éclaire ce que ce produit coûte, chez qui, et ce que la
 *  mise en concurrence a fait gagner. Les champs nullable (pas encore de
 *  fournisseur le moins cher, pas d'offre récente…) s'affichent « — »,
 *  jamais une valeur inventée. */
export function ProductScorecard({ productId }: { productId: string }) {
  const { data } = useProductOverview(productId);
  if (!data) return null;

  return (
    <div className="space-y-4">
      {/* Ligne de KPI : la dépense réelle, l'inflation et les économies, ce
          qu'on regarde d'abord. */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi
          icon={<TrendingUp className="h-5 w-5 text-primary" />}
          value={formatCurrency(data.annual_amount)}
          label="Payé sur 12 mois"
        />
        <TrendKpi pct={data.price_trend_pct} />
        <SavingsKpi
          realized={data.savings.realized}
          bestChoiceRate={data.savings.best_choice_rate}
          labels={data.savings.labels}
        />
      </div>

      {/* Volumes : achats, fournisseurs, recettes, offres. */}
      <Card>
        <CardContent className="flex flex-wrap gap-x-8 gap-y-2 py-4 text-sm">
          <Count n={data.purchase_count} label="achats" />
          <Count n={data.supplier_count} label="fournisseurs" />
          <Count n={data.recipe_count} label="recettes" />
          <Count n={data.offer_count} label="offres" />
        </CardContent>
      </Card>

      {/* Évolution mensuelle : barres simples, pas de librairie pour 12 points. */}
      {data.monthly.length > 1 ? <MonthlyBars monthly={data.monthly} /> : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <SafeBoundary>
          <Card>
            <CardContent className="py-4">
              <div className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                Moins cher
              </div>
              {data.cheapest_supplier ? (
                <div className="flex items-center justify-between gap-3 text-sm">
                  <Link
                    href={`/fournisseurs/${data.cheapest_supplier.supplier_id}`}
                    className="truncate hover:underline"
                  >
                    {data.cheapest_supplier.supplier_name ?? "Fournisseur"}
                  </Link>
                  <span className="tabular-nums font-medium">
                    {formatCurrency(data.cheapest_supplier.cost)}
                  </span>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">—</p>
              )}
            </CardContent>
          </Card>
        </SafeBoundary>

        <SafeBoundary>
          <Card>
            <CardContent className="py-4">
              <div className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                Offres
              </div>
              {data.offers ? (
                <div className="space-y-1.5 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground truncate">
                      Meilleure{data.offers.best_supplier_name ? ` · ${data.offers.best_supplier_name}` : ""}
                    </span>
                    <span className="tabular-nums font-medium">
                      {formatCurrency(data.offers.best_price)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">Dernière</span>
                    <span className="tabular-nums font-medium">
                      {formatCurrency(data.offers.latest_price)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">
                      Moyenne · {data.offers.supplier_count} fournisseur(s)
                    </span>
                    <span className="tabular-nums font-medium">
                      {formatCurrency(data.offers.avg_price)}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">—</p>
              )}
            </CardContent>
          </Card>
        </SafeBoundary>
      </div>

      {data.top_suppliers.length > 0 ? (
        <SafeBoundary>
          <Card>
            <CardContent className="py-4">
              <div className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                Fournisseurs
              </div>
              <ul className="space-y-1.5">
                {data.top_suppliers.slice(0, 6).map((s) => (
                  <li key={s.supplier_id} className="flex items-center justify-between gap-3 text-sm">
                    <Link
                      href={`/fournisseurs/${s.supplier_id}`}
                      className="flex min-w-0 items-center gap-2 truncate hover:underline"
                    >
                      <span className="truncate">{s.supplier_name ?? "Fournisseur"}</span>
                      {s.is_cheapest && (
                        <Badge variant="success" className="gap-1 shrink-0">
                          <Trophy className="h-3 w-3" /> Moins cher
                        </Badge>
                      )}
                    </Link>
                    <span className="tabular-nums font-medium">{formatCurrency(s.amount)}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </SafeBoundary>
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

function TrendKpi({ pct }: { pct: number | null }) {
  const tone =
    pct == null
      ? "text-muted-foreground"
      : pct > 0
        ? "text-red-600 dark:text-red-400"
        : "text-emerald-600 dark:text-emerald-400";
  const Icon = pct != null && pct < 0 ? TrendingDown : TrendingUp;
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4">
        <Icon className={cn("h-5 w-5", tone)} />
        <div className="min-w-0">
          <div className={cn("truncate text-lg font-bold tabular-nums", tone)}>
            {pct == null ? "—" : `${pct > 0 ? "+" : ""}${formatNumber(pct, 1)} %`}
          </div>
          <div className="text-xs text-muted-foreground">Inflation produit</div>
        </div>
      </CardContent>
    </Card>
  );
}

function SavingsKpi({
  realized,
  bestChoiceRate,
  labels,
}: {
  realized: number;
  bestChoiceRate: number | null;
  labels: { realized: string; best_choice_rate: string };
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4">
        <PiggyBank className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
        <div className="min-w-0">
          <div className="truncate text-lg font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
            {formatCurrency(realized)}
          </div>
          <div className="text-xs text-muted-foreground">
            {bestChoiceRate == null
              ? labels.realized
              : `${labels.best_choice_rate} · ${Math.round(bestChoiceRate * 100)} %`}
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
