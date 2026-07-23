"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Plus,
  Trash2,
  Loader2,
  Crown,
  Truck,
  ShieldCheck,
  PackageCheck,
} from "lucide-react";

import { BackButton } from "@/components/back-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useQuote,
  useQuoteComparison,
  useAddQuoteLine,
  useDeleteQuoteLine,
  useDeleteQuote,
  useOrderQuote,
} from "@/hooks/use-quotes";
import { useProducts } from "@/hooks/use-products";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { statusBadge } from "./quotes-view";
import type { QuoteComparisonSupplier } from "@/services/types";

const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

export function QuoteDetail({ quoteId }: { quoteId: string }) {
  const router = useRouter();
  const { data: quote, isLoading } = useQuote(quoteId);
  const hasRole = useAuthStore((s) => s.hasRole);
  const canWrite = hasRole("admin", "manager");
  const deleteQuote = useDeleteQuote();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Chargement…</p>;
  }
  if (!quote) {
    return (
      <div>
        <BackButton fallbackHref="/devis" />
        <p className="text-sm text-muted-foreground">Devis introuvable.</p>
      </div>
    );
  }

  const isDraft = (quote.status ?? "draft") === "draft";

  return (
    <div>
      <BackButton fallbackHref="/devis" />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-serif text-[24px] font-semibold tracking-tight">
              {quote.title?.trim() || quote.reference || "Devis"}
            </h1>
            {statusBadge(quote.status)}
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {quote.reference}
            {quote.supplier_name ? ` · Commandé chez ${quote.supplier_name}` : ""}
            {quote.total_amount != null
              ? ` · ${formatCurrency(quote.total_amount)}`
              : ""}
          </p>
        </div>
        {canWrite && isDraft ? (
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            onClick={() =>
              deleteQuote.mutate(quoteId, { onSuccess: () => router.push("/devis") })
            }
          >
            <Trash2 /> Supprimer
          </Button>
        ) : null}
      </div>

      <div className="grid gap-5">
        <LinesCard quoteId={quoteId} quote={quote} canWrite={canWrite && isDraft} />
        <ComparisonCard quoteId={quoteId} canOrder={canWrite && isDraft} />
      </div>
    </div>
  );
}

function LinesCard({
  quoteId,
  quote,
  canWrite,
}: {
  quoteId: string;
  quote: NonNullable<ReturnType<typeof useQuote>["data"]>;
  canWrite: boolean;
}) {
  const { data: products } = useProducts();
  const addLine = useAddQuoteLine(quoteId);
  const deleteLine = useDeleteQuoteLine(quoteId);
  const [productId, setProductId] = useState("");
  const [qty, setQty] = useState("");

  function add() {
    if (!productId) return;
    addLine.mutate(
      { product_id: productId, qty: qty.trim() === "" ? null : Number(qty.replace(",", ".")) },
      {
        onSuccess: () => {
          setProductId("");
          setQty("");
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Panier</CardTitle>
        <CardDescription>Les produits à sourcer et leurs quantités.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {quote.lines.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune ligne.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Produit</TableHead>
                <TableHead className="text-right">Quantité</TableHead>
                {quote.lines.some((l) => l.unit_price != null) ? (
                  <TableHead className="text-right">Prix retenu</TableHead>
                ) : null}
                {canWrite ? <TableHead className="w-10" /> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {quote.lines.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>
                    {l.product_id ? (
                      <Link
                        href={`/produits/${l.product_id}`}
                        className="font-medium hover:underline"
                      >
                        {l.product_name || "Produit"}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">
                        {l.description || "—"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(l.qty)}
                  </TableCell>
                  {quote.lines.some((x) => x.unit_price != null) ? (
                    <TableCell className="text-right tabular-nums">
                      {l.unit_price != null ? formatCurrency(l.unit_price) : "—"}
                    </TableCell>
                  ) : null}
                  {canWrite ? (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => deleteLine.mutate(l.id)}
                        aria-label="Supprimer la ligne"
                      >
                        <Trash2 className="text-muted-foreground" />
                      </Button>
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {canWrite ? (
          <div className="flex items-center gap-2 border-t border-border/50 pt-3">
            <select
              className={SELECT_CLASS}
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
            >
              <option value="">— ajouter un produit —</option>
              {(products ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <Input
              className="w-24"
              inputMode="decimal"
              placeholder="Qté"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
            />
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={add}
              disabled={!productId || addLine.isPending}
            >
              <Plus /> Ajouter
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ComparisonCard({
  quoteId,
  canOrder,
}: {
  quoteId: string;
  canOrder: boolean;
}) {
  const { data, isLoading, isError } = useQuoteComparison(quoteId);
  const order = useOrderQuote(quoteId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Comparaison des fournisseurs</CardTitle>
        <CardDescription>
          Coût du panier par fournisseur, à partir des derniers prix connus.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Calcul en cours…</p>
        ) : isError ? (
          <p className="text-sm text-muted-foreground">
            Comparaison indisponible.
          </p>
        ) : !data || data.suppliers.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun fournisseur ne peut chiffrer ce panier. Ajoutez des prix
            (via une facture) ou associez des fournisseurs aux produits.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fournisseur</TableHead>
                  <TableHead>Couverture</TableHead>
                  <TableHead>Délai</TableHead>
                  <TableHead className="text-right">Total panier</TableHead>
                  {canOrder ? <TableHead className="text-right">Action</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.suppliers.map((s) => (
                  <SupplierRow
                    key={s.supplier_id}
                    s={s}
                    priceable={data.priceable_count}
                    canOrder={canOrder}
                    ordering={order.isPending}
                    onOrder={() => order.mutate(s.supplier_id)}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SupplierRow({
  s,
  priceable,
  canOrder,
  ordering,
  onOrder,
}: {
  s: QuoteComparisonSupplier;
  priceable: number;
  canOrder: boolean;
  ordering: boolean;
  onOrder: () => void;
}) {
  return (
    <TableRow className={s.is_cheapest ? "bg-emerald-500/5" : undefined}>
      <TableCell>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium">{s.supplier_name || "Fournisseur"}</span>
          {s.is_cheapest ? (
            <Badge variant="success" className="gap-1">
              <Crown className="h-3 w-3" /> Moins cher
            </Badge>
          ) : null}
          {s.preferred ? (
            <Badge variant="secondary" className="gap-1">
              <ShieldCheck className="h-3 w-3" /> Préféré
            </Badge>
          ) : null}
          {!s.is_cheapest && s.is_best_coverage && !s.is_full_coverage ? (
            <Badge variant="outline" className="gap-1">
              <PackageCheck className="h-3 w-3" /> Meilleure couverture
            </Badge>
          ) : null}
        </div>
      </TableCell>
      <TableCell>
        {s.is_full_coverage ? (
          <span className="text-sm text-emerald-600 dark:text-emerald-400">
            Complète
          </span>
        ) : (
          <span
            className="text-sm text-amber-600 dark:text-amber-400"
            title={s.missing.map((m) => m.product_name || m.product_id).join(", ")}
          >
            {s.covered_count}/{priceable}
          </span>
        )}
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {s.max_lead_time_days != null ? (
          <span className="inline-flex items-center gap-1">
            <Truck className="h-3.5 w-3.5" />
            {s.max_lead_time_days} j
          </span>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="text-right font-semibold tabular-nums">
        {formatCurrency(s.total)}
      </TableCell>
      {canOrder ? (
        <TableCell className="text-right">
          <Button
            size="sm"
            variant={s.is_cheapest ? "gradient" : "outline"}
            onClick={onOrder}
            disabled={ordering}
          >
            {ordering ? <Loader2 className="animate-spin" /> : null}
            Commander
          </Button>
        </TableCell>
      ) : null}
    </TableRow>
  );
}
