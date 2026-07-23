"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, ShieldCheck, Trash2, Truck } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { BackButton } from "@/components/back-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDeleteReceipt,
  useQualityVocabulary,
  useReceipt,
  useReceiptControl,
  useValidateReceipt,
} from "@/hooks/use-receipts";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatDate, formatNumber, cn } from "@/lib/utils";
import type { ReceiptControl } from "@/services/types";

/** Ce qui ne se lit pas ligne par ligne : le document lui-même. */
const DOCUMENT_ANOMALIES: Record<string, string> = {
  supplier: "Livré par un autre fournisseur que celui commandé",
};

const LINE_ANOMALIES: Record<string, string> = {
  price: "Prix différent de la commande",
  pack_size: "Conditionnement différent",
  product: "Produit remplacé",
  quality: "Marchandise refusée ou détruite",
  unordered: "Livré hors commande",
};

export function ReceiptDetail({ receiptId }: { receiptId: string }) {
  const { data: receipt, isLoading } = useReceipt(receiptId);
  const { data: control } = useReceiptControl(receiptId);
  const { data: vocabulary } = useQualityVocabulary();
  const validate = useValidateReceipt();
  const remove = useDeleteReceipt();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));

  if (isLoading) {
    return (
      <>
        <BackButton fallbackHref="/receptions" />
        <Skeleton className="h-40 w-full" />
      </>
    );
  }
  if (!receipt) {
    return (
      <>
        <BackButton fallbackHref="/receptions" />
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Réception introuvable.
          </CardContent>
        </Card>
      </>
    );
  }

  const frozen = receipt.status === "checked";
  const reasonLabel = (v: string) =>
    vocabulary?.reasons.find((r) => r.value === v)?.label ?? v;

  return (
    <>
      <BackButton fallbackHref="/receptions" />
      <PageHeader
        title={receipt.reference ?? "Réception"}
        description={`${receipt.supplier_name ?? "Fournisseur"}${
          receipt.order_reference ? ` · commande ${receipt.order_reference}` : ""
        }`}
      />

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-3 py-5">
          <Badge
            className={cn(
              "border-0",
              frozen
                ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                : "bg-muted text-muted-foreground",
            )}
          >
            {frozen ? <ShieldCheck className="mr-1 h-3.5 w-3.5" /> : null}
            {receipt.status_label}
          </Badge>
          {receipt.received_at ? (
            <Field label="Reçue le" value={formatDate(receipt.received_at)} />
          ) : null}
          {receipt.delivery_note_number ? (
            <Field label="Bon de livraison" value={receipt.delivery_note_number} />
          ) : null}
          {/* La traçabilité : ces trois lignes sont ce qu'on oppose au
              fournisseur trois semaines plus tard. */}
          {receipt.received_by_name ? (
            <Field label="Réceptionné par" value={receipt.received_by_name} />
          ) : null}
          {receipt.checked_by_name ? (
            <Field
              label="Contrôlé par"
              value={`${receipt.checked_by_name}${
                receipt.checked_at ? ` · ${formatDate(receipt.checked_at)}` : ""
              }`}
            />
          ) : null}
          {receipt.device_info ? (
            <Field label="Saisi sur" value={receipt.device_info} />
          ) : null}

          {canWrite && !frozen ? (
            <div className="ml-auto flex gap-2">
              <Button variant="ghost" size="sm" onClick={() => remove.mutate(receipt.id)}>
                <Trash2 className="h-4 w-4" />
                <span className="ml-1">Supprimer</span>
              </Button>
              <Button size="sm" onClick={() => validate.mutate(receipt.id)}>
                <CheckCircle2 className="h-4 w-4" />
                <span className="ml-1">Valider</span>
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {receipt.notes ? (
        <p className="mb-4 text-[13px] text-muted-foreground">
          <span className="font-medium text-foreground">Observations :</span> {receipt.notes}
        </p>
      ) : null}

      {control ? <ControlSummary control={control} /> : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lignes reçues</CardTitle>
          <CardDescription>
            Accepté, refusé et détruit sont calculés depuis les anomalies — rien
            n&apos;est saisi deux fois.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {receipt.lines.map((line) => (
            <div key={line.id} className="rounded-xl border border-border/60 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium">
                    {line.product_id ? (
                      <Link href={`/produits/${line.product_id}`} className="hover:underline">
                        {line.product_name ?? line.description}
                      </Link>
                    ) : (
                      (line.product_name ?? line.description ?? "Ligne")
                    )}
                  </div>
                  {line.substituted_product_name ? (
                    <div className="text-[12.5px] text-primary">
                      remplacé par {line.substituted_product_name}
                    </div>
                  ) : null}
                </div>
                <Badge variant="outline">{line.state_label}</Badge>
              </div>

              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13px]">
                <span>
                  livré <strong className="tabular-nums">{formatNumber(line.qty_delivered, 0)}</strong>
                </span>
                <span className="text-emerald-600 dark:text-emerald-400">
                  accepté <strong className="tabular-nums">{formatNumber(line.qty_accepted, 0)}</strong>
                </span>
                {(line.qty_rejected ?? 0) > 0 ? (
                  <span className="text-red-600 dark:text-red-400">
                    refusé <strong className="tabular-nums">{formatNumber(line.qty_rejected, 0)}</strong>
                  </span>
                ) : null}
                {(line.qty_destroyed ?? 0) > 0 ? (
                  <span className="text-red-600 dark:text-red-400">
                    détruit <strong className="tabular-nums">{formatNumber(line.qty_destroyed, 0)}</strong>
                  </span>
                ) : null}
              </div>

              {line.issues.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {line.issues.map((issue, i) => (
                    <li key={i} className="flex flex-wrap items-center gap-2 text-[13px]">
                      <AlertTriangle className="h-3.5 w-3.5 flex-none text-amber-600 dark:text-amber-400" />
                      <span>
                        {issue.qty != null ? `${formatNumber(issue.qty, 0)} × ` : ""}
                        {issue.reason_label ?? reasonLabel(issue.reason)}
                      </span>
                      <Badge variant="secondary" className="text-[11px]">
                        {issue.outcome_label ?? issue.outcome}
                      </Badge>
                      {issue.notes ? (
                        <span className="text-muted-foreground">— {issue.notes}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}

              {line.photos.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {line.photos.map((p, i) => (
                    <a
                      key={i}
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[12.5px] text-primary underline underline-offset-4"
                    >
                      {p.caption ?? `photo ${i + 1}`}
                    </a>
                  ))}
                </div>
              ) : null}

              {line.notes ? (
                <p className="mt-2 text-[12.5px] text-muted-foreground">{line.notes}</p>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}

function ControlSummary({ control }: { control: ReceiptControl }) {
  if (control.issue_count === 0) {
    return (
      <Card className="mb-4 border-emerald-500/40">
        <CardContent className="flex items-center gap-2 py-4 text-sm">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          Livraison conforme à la commande.
        </CardContent>
      </Card>
    );
  }
  const short = control.lines.filter((l) => l.qty_remaining > 0.001);
  return (
    <Card className="mb-4 border-amber-500/40">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          {control.issue_count} anomalie(s) au contrôle
        </CardTitle>
        {control.missing_value > 0 ? (
          <CardDescription>
            {formatCurrency(control.missing_value)} de marchandise manquante ou refusée.
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-1.5 text-[13px]">
        {control.document_anomalies.map((a) => (
          <div key={a} className="flex items-center gap-2">
            <Truck className="h-3.5 w-3.5 flex-none text-red-600 dark:text-red-400" />
            {DOCUMENT_ANOMALIES[a] ?? a}
          </div>
        ))}
        {short.map((l) => (
          <div key={l.order_line_id ?? l.description} className="flex flex-wrap items-center gap-x-2">
            <span className="font-medium">{l.description}</span>
            <span className="text-amber-600 dark:text-amber-400">
              reste dû {formatNumber(l.qty_remaining, 0)}
              {l.missing_value ? ` · ${formatCurrency(l.missing_value)}` : ""}
            </span>
          </div>
        ))}
        {control.lines
          .filter((l) => l.anomalies.length > 0)
          .map((l) => (
            <div key={`a-${l.order_line_id ?? l.description}`} className="flex flex-wrap items-center gap-x-2">
              <span className="font-medium">{l.description}</span>
              <span className="text-muted-foreground">
                {l.anomalies.map((a) => LINE_ANOMALIES[a] ?? a).join(" · ")}
              </span>
            </div>
          ))}
      </CardContent>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11.5px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}
