"use client";

import Link from "next/link";
import { CheckCircle2, AlertTriangle, TrendingUp, TrendingDown, Percent } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useInvoiceQuoteVariance } from "@/hooks/use-invoices";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";
import type { VarianceLine, VarianceStatus } from "@/services/types";

/**
 * Contrôle prévu / facturé (§9) : ce que le fournisseur facture, comparé au
 * devis qui a été accepté. Sur une facture de 40 lignes, une hausse de 3 % ne
 * se voit pas à l'œil nu.
 */
const LABEL: Record<VarianceStatus, string> = {
  ok: "Conforme",
  price_up: "Prix en hausse",
  price_down: "Prix en baisse",
  qty_diff: "Quantité différente",
  missing: "Non facturé",
  extra: "Hors devis",
};

function statusTone(s: VarianceStatus) {
  switch (s) {
    case "price_up":
    case "extra":
      return "text-red-700 dark:text-red-300 bg-red-500/10 ring-1 ring-inset ring-red-500/20";
    case "price_down":
      return "text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 ring-1 ring-inset ring-emerald-500/25";
    case "qty_diff":
    case "missing":
      return "text-amber-700 dark:text-amber-300 bg-amber-500/10 ring-1 ring-inset ring-amber-500/20";
    default:
      return "text-muted-foreground bg-muted/50";
  }
}

export function QuoteVarianceCard({ invoiceId }: { invoiceId: string }) {
  const { data, isLoading } = useInvoiceQuoteVariance(invoiceId);

  // Aucun devis rattaché : on n'affiche rien plutôt qu'un bloc vide qui
  // laisserait croire à un contrôle alors qu'il n'y a rien à contrôler.
  if (isLoading || !data?.linked) return null;

  const issues = (data.lines ?? []).filter((l) => l.status !== "ok" || l.vat_mismatch);
  const conform = data.is_conform;
  const delta = data.total_delta ?? 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          {conform ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          )}
          Contrôle devis / facture
          {data.quote_reference ? (
            <Link
              href={`/devis/${data.quote_id}`}
              className="text-sm font-normal text-primary underline underline-offset-4"
            >
              {data.quote_reference}
            </Link>
          ) : null}
        </CardTitle>
        <CardDescription>
          {conform ? (
            <>La facture est conforme au devis accepté.</>
          ) : (
            <>
              {data.issue_count} ligne(s) s&apos;écartent du devis —{" "}
              <span
                className={cn(
                  "font-semibold",
                  delta > 0
                    ? "text-red-600 dark:text-red-400"
                    : "text-emerald-600 dark:text-emerald-400",
                )}
              >
                {delta > 0 ? "+" : ""}
                {formatCurrency(delta)}
                {data.total_delta_pct != null
                  ? ` (${delta > 0 ? "+" : ""}${formatNumber(data.total_delta_pct, 1)} %)`
                  : ""}
              </span>{" "}
              sur {formatCurrency(data.quoted_total ?? 0)} devisés.
            </>
          )}
        </CardDescription>
      </CardHeader>

      {issues.length > 0 ? (
        <CardContent className="space-y-2">
          {issues.map((l, i) => (
            <VarianceRow key={`${l.product_id ?? l.product_name}-${i}`} line={l} />
          ))}
        </CardContent>
      ) : null}
    </Card>
  );
}

function VarianceRow({ line }: { line: VarianceLine }) {
  const q = line.quoted;
  const b = line.billed;
  return (
    <div className="rounded-lg border border-border/50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{line.product_name ?? "Ligne"}</span>
        <Badge className={cn("border-0", statusTone(line.status))}>
          {LABEL[line.status]}
        </Badge>
        {line.vat_mismatch ? (
          <Badge variant="outline" className="gap-1">
            <Percent className="h-3 w-3" /> TVA {formatNumber(q.vat_rate, 1)} →{" "}
            {formatNumber(b.vat_rate, 1)} %
          </Badge>
        ) : null}
        {line.total_delta ? (
          <span
            className={cn(
              "ml-auto inline-flex items-center gap-1 text-sm font-semibold tabular-nums",
              line.total_delta > 0
                ? "text-red-600 dark:text-red-400"
                : "text-emerald-600 dark:text-emerald-400",
            )}
          >
            {line.total_delta > 0 ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5" />
            )}
            {line.total_delta > 0 ? "+" : ""}
            {formatCurrency(line.total_delta)}
          </span>
        ) : null}
      </div>

      <div className="mt-1.5 grid gap-x-6 gap-y-0.5 text-[12.5px] text-muted-foreground sm:grid-cols-2">
        <div>
          <span className="font-medium text-foreground/80">Devisé</span> ·{" "}
          {q.unit_price != null ? formatCurrency(q.unit_price) : "—"}
          {q.qty != null ? ` × ${formatNumber(q.qty)}` : ""}
          {q.total != null ? ` = ${formatCurrency(q.total)}` : ""}
        </div>
        <div>
          <span className="font-medium text-foreground/80">Facturé</span> ·{" "}
          {b.unit_price != null ? formatCurrency(b.unit_price) : "—"}
          {b.qty != null ? ` × ${formatNumber(b.qty)}` : ""}
          {b.total != null ? ` = ${formatCurrency(b.total)}` : ""}
          {line.price_delta_pct ? (
            <span className="ml-1 font-semibold">
              ({line.price_delta_pct > 0 ? "+" : ""}
              {formatNumber(line.price_delta_pct, 1)} %)
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
