"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useInvoiceControl } from "@/hooks/use-invoices";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";
import type { ControlFlag, InvoiceControlLine } from "@/services/types";

/** Contrôle facture : commandé → livré → facturé.
 *
 *  Ne s'affiche que si la facture est rattachée à une commande. Quand tout
 *  concorde, un bandeau d'une ligne suffit ; sinon on liste les seules lignes
 *  qui posent problème, l'anomalie la plus grave en tête. */
const FLAG_LABELS: Record<ControlFlag, string> = {
  billed_not_received: "Facturé mais non reçu",
  extra: "Facturé hors commande",
  over_billed: "Facturé plus que reçu",
  not_received: "Commandé, pas encore reçu",
  price_up: "Prix en hausse",
  vat_diff: "TVA différente",
  qty_diff: "Quantité différente du reçu",
  price_down: "Prix en baisse",
  missing: "Reçu mais pas encore facturé",
};

/** Les deux drapeaux où l'on paie pour une marchandise qu'on n'a pas. */
const GRAVE: ControlFlag[] = ["billed_not_received", "over_billed", "extra"];

function flagTone(status: string) {
  if (GRAVE.includes(status as ControlFlag))
    return "bg-red-500/15 text-red-700 dark:text-red-300";
  if (status === "price_down" || status === "missing")
    return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
  return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
}

export function InvoiceControlCard({ invoiceId }: { invoiceId: string }) {
  const { data } = useInvoiceControl(invoiceId);
  if (!data || data.linked !== true) return null;

  const conform = data.is_conform === true;
  const issues = (data.lines ?? []).filter((l) => l.status !== "ok");
  const graveCount = data.billed_not_received_count ?? 0;

  return (
    <Card
      className={cn(
        "mt-4",
        conform ? "border-emerald-500/40" : graveCount > 0 ? "border-red-500/50" : "border-amber-500/40",
      )}
    >
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          {conform ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          ) : graveCount > 0 ? (
            <ShieldAlert className="h-5 w-5 text-red-600 dark:text-red-400" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          )}
          Contrôle commande → livraison → facture
          {data.order_reference ? (
            <Link
              href={`/commandes/${data.order_id}`}
              className="text-[13px] font-normal text-primary underline underline-offset-4"
            >
              {data.order_reference}
            </Link>
          ) : null}
        </CardTitle>
        <CardDescription>
          {conform ? (
            "La facture est fidèle à ce qui a été commandé et livré."
          ) : (
            <>
              {data.issue_count} ligne(s) s&apos;écartent
              {data.total_delta ? (
                <>
                  {" "}·{" "}
                  <span
                    className={cn(
                      "font-semibold",
                      (data.total_delta ?? 0) > 0
                        ? "text-red-600 dark:text-red-400"
                        : "text-emerald-600 dark:text-emerald-400",
                    )}
                  >
                    {(data.total_delta ?? 0) > 0 ? "+" : ""}
                    {formatCurrency(data.total_delta)}
                  </span>{" "}
                  vs commandé
                </>
              ) : null}
              {graveCount > 0 ? (
                <span className="ml-1 font-semibold text-red-600 dark:text-red-400">
                  · {graveCount} facturée(s) sans être reçue(s)
                </span>
              ) : null}
            </>
          )}
        </CardDescription>
      </CardHeader>

      {!conform ? (
        <CardContent className="space-y-2">
          {issues.map((line, i) => (
            <ControlRow key={line.product_id ?? line.description ?? i} line={line} />
          ))}
        </CardContent>
      ) : null}
    </Card>
  );
}

function ControlRow({ line }: { line: InvoiceControlLine }) {
  return (
    <div className={cn("rounded-lg px-3 py-2", flagTone(line.status))}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{line.description}</span>
        <div className="flex flex-wrap gap-1">
          {line.flags.map((f) => (
            <Badge key={f} variant="outline" className="border-current/30 text-[11px]">
              {FLAG_LABELS[f]}
            </Badge>
          ))}
        </div>
      </div>
      {/* Les trois colonnes, côte à côte : c'est la lecture de tout le module. */}
      <div className="mt-1 flex flex-wrap gap-x-4 text-[12.5px] opacity-90">
        <span>
          commandé{" "}
          {line.ordered
            ? `${formatNumber(line.ordered.qty, 0)} × ${formatCurrency(line.ordered.unit_price)}`
            : "—"}
        </span>
        <span>livré {line.received ? formatNumber(line.received.qty, 0) : "—"}</span>
        <span>
          facturé{" "}
          {line.billed
            ? `${formatNumber(line.billed.qty, 0)} × ${formatCurrency(line.billed.unit_price)}`
            : "—"}
        </span>
      </div>
    </div>
  );
}
