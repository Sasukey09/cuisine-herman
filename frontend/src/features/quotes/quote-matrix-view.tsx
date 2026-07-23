"use client";

import Link from "next/link";
import { Crown, Truck, PiggyBank, AlertTriangle, ShieldCheck } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { BackButton } from "@/components/back-button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useQuoteMatrix } from "@/hooks/use-quotes";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";
import type { MatrixOffer, MatrixProduct, QuoteMatrix } from "@/services/types";

/** Vert = meilleure offre · orange = intermédiaire · rouge = la plus chère.
 *  Gris = hors classement (offre périmée ou produit indisponible). */
function cellTone(rank: MatrixOffer["rank"]) {
  switch (rank) {
    case "best":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-1 ring-inset ring-emerald-500/25";
    case "worst":
      return "bg-red-500/10 text-red-700 dark:text-red-300 ring-1 ring-inset ring-red-500/20";
    case "mid":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-1 ring-inset ring-amber-500/20";
    default:
      return "bg-muted/40 text-muted-foreground";
  }
}

function priceOf(offer: MatrixOffer, product: MatrixProduct) {
  return product.basis === "base_unit" ? offer.price_per_base_unit : offer.unit_price;
}

export function QuoteMatrixView() {
  const { data, isLoading, isError } = useQuoteMatrix("draft");

  if (isLoading) {
    return (
      <>
        <BackButton fallbackHref="/devis" />
        <PageHeader title="Comparatif des devis" />
        <p className="text-sm text-muted-foreground">Calcul en cours…</p>
      </>
    );
  }

  if (isError || !data || data.products.length === 0) {
    return (
      <>
        <BackButton fallbackHref="/devis" />
        <PageHeader
          title="Comparatif des devis"
          description="Comparez vos devis en cours, produit par produit."
        />
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Aucun devis en cours à comparer.{" "}
            <Link href="/devis/import" className="text-primary underline underline-offset-4">
              Importez un devis
            </Link>{" "}
            pour commencer.
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <BackButton fallbackHref="/devis" />
      <PageHeader
        title="Comparatif des devis"
        description="Une ligne par produit, une colonne par fournisseur. Les prix sont ramenés à l'unité de base pour être comparables."
      />
      <Kpis data={data} />
      <MatrixTable data={data} />
      <Legend />
    </>
  );
}

function Kpis({ data }: { data: QuoteMatrix }) {
  const cheapest = data.suppliers.find((s) => s.supplier_id === data.cheapest_supplier_id);
  const fastest = data.suppliers.find((s) => s.supplier_id === data.fastest_supplier_id);
  return (
    <div className="mb-5 grid gap-3 sm:grid-cols-3">
      <Card>
        <CardContent className="flex items-center gap-3 py-4">
          <Crown className="h-5 w-5 flex-none text-emerald-600 dark:text-emerald-400" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">
              {cheapest?.supplier_name ?? "—"}
            </div>
            <div className="text-xs text-muted-foreground">
              Le moins cher · {cheapest ? formatCurrency(cheapest.total_with_delivery) : "—"}
              {/* Le port est intégré au classement : l'afficher évite de faire
                  douter l'utilisateur qui recompte le panier à la main. */}
              {cheapest?.delivery_fee ? (
                <span title="Frais de livraison inclus dans le total">
                  {" "}(dont {formatCurrency(cheapest.delivery_fee)} de port)
                </span>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex items-center gap-3 py-4">
          <Truck className="h-5 w-5 flex-none text-primary" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">
              {fastest?.supplier_name ?? "—"}
            </div>
            <div className="text-xs text-muted-foreground">
              Le plus rapide
              {fastest?.max_lead_time_days != null ? ` · ${fastest.max_lead_time_days} j` : ""}
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex items-center gap-3 py-4">
          <PiggyBank className="h-5 w-5 flex-none text-amber-600 dark:text-amber-400" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">
              {formatCurrency(data.potential_savings)}
            </div>
            <div className="text-xs text-muted-foreground">
              Économies possibles · {data.product_count} produit(s)
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MatrixTable({ data }: { data: QuoteMatrix }) {
  const suppliers = data.suppliers;
  return (
    <div className="overflow-x-auto rounded-xl border border-border/60 bg-card shadow-sm">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border/60 bg-muted/40">
            <th className="sticky left-0 z-10 bg-muted/40 px-4 py-3 text-left text-[11.5px] font-bold uppercase tracking-wider text-muted-foreground">
              Produit
            </th>
            {suppliers.map((s) => (
              <th key={s.supplier_id} className="px-3 py-3 text-left align-bottom">
                <div className="flex items-center gap-1.5 text-[13px] font-semibold text-foreground">
                  <span className="truncate">{s.supplier_name ?? "Fournisseur"}</span>
                  {s.supplier_id === data.cheapest_supplier_id ? (
                    <Crown className="h-3.5 w-3.5 flex-none text-emerald-600 dark:text-emerald-400" />
                  ) : null}
                  {s.preferred ? (
                    <ShieldCheck className="h-3.5 w-3.5 flex-none text-primary" />
                  ) : null}
                </div>
                <div className="mt-0.5 text-[11px] font-normal text-muted-foreground">
                  {s.best_count} meilleure(s) · {s.covered}/{data.product_count}
                  {s.max_lead_time_days != null ? ` · ${s.max_lead_time_days} j` : ""}
                </div>
                <div className="mt-0.5 text-[11px] font-normal tabular-nums text-muted-foreground">
                  {formatCurrency(s.total_with_delivery)}
                  {s.delivery_fee ? (
                    <span className="ml-1 text-amber-600 dark:text-amber-400">
                      +{formatCurrency(s.delivery_fee)} port
                    </span>
                  ) : null}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.products.map((p) => (
            <tr key={p.product_id} className="border-b border-border/40 last:border-0">
              <th className="sticky left-0 z-10 max-w-[240px] bg-card px-4 py-3 text-left align-top font-medium">
                <Link
                  href={`/produits/${p.product_id}`}
                  className="hover:underline"
                >
                  {p.product_name ?? "Produit"}
                </Link>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] font-normal text-muted-foreground">
                  {p.basis === "base_unit" ? (
                    <span>prix / {p.offers.find((o) => o.base_unit)?.base_unit ?? "unité"}</span>
                  ) : (
                    <span
                      className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400"
                      title="Conditionnements non comparables : le classement se fait sur le prix affiché."
                    >
                      <AlertTriangle className="h-3 w-3" /> prix affiché
                    </span>
                  )}
                  {p.history.last_paid != null ? (
                    <span>
                      · payé {formatCurrency(p.history.last_paid)}
                      {p.vs_last_paid_pct != null ? (
                        <span
                          className={cn(
                            "ml-1 font-semibold",
                            p.vs_last_paid_pct <= 0
                              ? "text-emerald-600 dark:text-emerald-400"
                              : "text-red-600 dark:text-red-400",
                          )}
                        >
                          {p.vs_last_paid_pct > 0 ? "+" : ""}
                          {formatNumber(p.vs_last_paid_pct, 1)} %
                        </span>
                      ) : null}
                    </span>
                  ) : null}
                </div>
              </th>
              {suppliers.map((s) => {
                const offer = p.offers.find((o) => o.supplier_id === s.supplier_id);
                return (
                  <td key={s.supplier_id} className="px-3 py-3 align-top">
                    {offer ? <OfferCell offer={offer} product={p} /> : <NoOffer />}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OfferCell({ offer, product }: { offer: MatrixOffer; product: MatrixProduct }) {
  const price = priceOf(offer, product);
  return (
    <div className={cn("rounded-lg px-2.5 py-2", cellTone(offer.rank))}>
      <div className="flex items-baseline gap-1.5">
        <span className="font-semibold tabular-nums">
          {price != null ? formatCurrency(price) : "—"}
        </span>
        {offer.delta_pct_vs_best ? (
          <span className="text-[11px] tabular-nums opacity-80">
            +{formatNumber(offer.delta_pct_vs_best, 1)} %
          </span>
        ) : null}
      </div>
      <div className="mt-0.5 space-y-0.5 text-[11px] opacity-90">
        {offer.unit_price != null && product.basis === "base_unit" ? (
          <div>{formatCurrency(offer.unit_price)} / {offer.pack_size ?? "unité"}</div>
        ) : offer.pack_size ? (
          <div>{offer.pack_size}</div>
        ) : null}
        <div className="flex flex-wrap gap-x-2">
          {offer.vat_rate != null ? <span>TVA {formatNumber(offer.vat_rate, 1)} %</span> : null}
          {offer.discount_pct ? <span>−{formatNumber(offer.discount_pct, 1)} %</span> : null}
          {offer.lead_time_days != null ? <span>{offer.lead_time_days} j</span> : null}
          {offer.min_qty ? <span>min. {formatNumber(offer.min_qty, 0)}</span> : null}
        </div>
        {offer.brand ? <div className="truncate italic">{offer.brand}</div> : null}
        {offer.expired ? (
          <Badge variant="destructive" className="mt-1">Périmée</Badge>
        ) : !offer.available ? (
          <Badge variant="outline" className="mt-1">Indisponible</Badge>
        ) : null}
      </div>
    </div>
  );
}

function NoOffer() {
  return (
    <div className="rounded-lg border border-dashed border-border/60 px-2.5 py-2 text-[11.5px] text-muted-foreground">
      pas d&apos;offre
    </div>
  );
}

function Legend() {
  return (
    <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500/40" /> meilleure offre
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-amber-500/40" /> intermédiaire
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-red-500/40" /> la plus chère
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-muted" /> hors classement (périmée / indisponible)
      </span>
    </p>
  );
}
