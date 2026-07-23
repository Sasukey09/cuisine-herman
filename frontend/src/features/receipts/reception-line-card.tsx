"use client";

import { Camera, Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";
import type {
  IssueOutcome,
  IssueReason,
  QualityVocabulary,
  ReceiptLine,
} from "@/services/types";

const SELECT =
  "h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

/** Ce que le serveur calculera. Recalculé ici pour que le réceptionnaire voie
 *  l'effet de sa saisie sans aller-retour — le serveur reste la référence, et
 *  ces deux calculs sont volontairement la même règle. */
export function lineTotals(line: ReceiptLine) {
  const delivered = line.qty_delivered ?? 0;
  let rejected = 0;
  let destroyed = 0;
  let flagged = 0;
  for (const i of line.issues) {
    // Anomalie sans quantité : elle porte sur toute la ligne.
    const qty = i.qty ?? delivered;
    flagged += qty;
    if (i.outcome === "rejected") rejected += qty;
    if (i.outcome === "destroyed") destroyed += qty;
  }
  const lost = Math.min(rejected + destroyed, delivered);
  const accepted = Math.max(delivered - lost, 0);
  const state = line.substituted_product_id
    ? "Remplacée"
    : delivered <= 0
      ? "En attente"
      : accepted <= 0
        ? "Refusée"
        : flagged > 0
          ? "Partiellement conforme"
          : "Conforme";
  return { delivered, accepted, rejected: Math.min(rejected, delivered), destroyed, state };
}

function stateTone(state: string) {
  switch (state) {
    case "Conforme":
      return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
    case "Partiellement conforme":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
    case "Refusée":
      return "bg-red-500/15 text-red-700 dark:text-red-300";
    case "Remplacée":
      return "bg-primary/15 text-primary";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function ReceptionLineCard({
  line,
  ordered,
  alreadyReceived,
  vocabulary,
  onChange,
  readOnly = false,
}: {
  line: ReceiptLine;
  ordered?: number | null;
  alreadyReceived?: number;
  vocabulary?: QualityVocabulary;
  onChange: (patch: Partial<ReceiptLine>) => void;
  readOnly?: boolean;
}) {
  const totals = lineTotals(line);
  const remaining = (ordered ?? 0) - (alreadyReceived ?? 0) - totals.accepted;

  function addIssue() {
    onChange({
      issues: [
        ...line.issues,
        { qty: null, reason: "product_damaged" as IssueReason, outcome: "rejected" as IssueOutcome },
      ],
    });
  }
  function patchIssue(i: number, patch: Partial<(typeof line.issues)[number]>) {
    onChange({ issues: line.issues.map((it, k) => (k === i ? { ...it, ...patch } : it)) });
  }
  function removeIssue(i: number) {
    onChange({ issues: line.issues.filter((_, k) => k !== i) });
  }

  return (
    <div className="rounded-xl border border-border/60 bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-semibold">
            {line.product_name ?? line.description ?? "Ligne"}
          </div>
          <div className="mt-0.5 text-[12.5px] text-muted-foreground">
            {ordered != null ? `commandé ${formatNumber(ordered, 0)}` : "hors commande"}
            {alreadyReceived ? ` · déjà reçu ${formatNumber(alreadyReceived, 0)}` : ""}
            {line.pack_size ? ` · ${line.pack_size}` : ""}
            {line.unit_price != null ? ` · ${formatCurrency(line.unit_price)}` : ""}
          </div>
        </div>
        <Badge className={cn("border-0", stateTone(totals.state))}>{totals.state}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor={`qty-${line.order_line_id ?? line.id}`}>Livré</Label>
          <Input
            id={`qty-${line.order_line_id ?? line.id}`}
            type="number"
            min={0}
            className="w-24"
            disabled={readOnly}
            value={line.qty_delivered ?? ""}
            onChange={(e) =>
              onChange({
                qty_delivered: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
        </div>
        {/* Accepté / refusé / détruit ne se saisissent pas : ils se déduisent
            des anomalies. Les afficher évite de faire recompter. */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 pb-1.5 text-[13px]">
          <span>
            accepté{" "}
            <span className="font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
              {formatNumber(totals.accepted, 0)}
            </span>
          </span>
          {totals.rejected > 0 ? (
            <span>
              refusé{" "}
              <span className="font-semibold tabular-nums text-red-600 dark:text-red-400">
                {formatNumber(totals.rejected, 0)}
              </span>
            </span>
          ) : null}
          {totals.destroyed > 0 ? (
            <span>
              détruit{" "}
              <span className="font-semibold tabular-nums text-red-600 dark:text-red-400">
                {formatNumber(totals.destroyed, 0)}
              </span>
            </span>
          ) : null}
          {ordered != null && remaining > 0.001 ? (
            <span className="text-amber-600 dark:text-amber-400">
              reste dû <span className="font-semibold tabular-nums">{formatNumber(remaining, 0)}</span>
            </span>
          ) : null}
        </div>
      </div>

      {line.issues.length > 0 ? (
        <div className="mt-3 space-y-2">
          {line.issues.map((issue, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/40 p-2">
              <Input
                type="number"
                min={0}
                placeholder="tout"
                title="Quantité concernée — vide = toute la ligne"
                className="w-20"
                disabled={readOnly}
                value={issue.qty ?? ""}
                onChange={(e) =>
                  patchIssue(i, { qty: e.target.value === "" ? null : Number(e.target.value) })
                }
              />
              <select
                className={cn(SELECT, "min-w-44 flex-1")}
                disabled={readOnly}
                value={issue.reason}
                onChange={(e) => patchIssue(i, { reason: e.target.value as IssueReason })}
                aria-label="Motif"
              >
                {vocabulary?.reasons.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <select
                className={cn(SELECT, "w-48")}
                disabled={readOnly}
                value={issue.outcome}
                onChange={(e) => patchIssue(i, { outcome: e.target.value as IssueOutcome })}
                aria-label="Décision"
              >
                {vocabulary?.outcomes.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              {!readOnly ? (
                <Button variant="ghost" size="icon" onClick={() => removeIssue(i)} aria-label="Retirer">
                  <Trash2 className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {!readOnly ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={addIssue}>
            <Plus className="h-4 w-4" />
            <span className="ml-1">Signaler une anomalie</span>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              const url = window.prompt("Adresse de la photo");
              if (url) onChange({ photos: [...line.photos, { url }] });
            }}
          >
            <Camera className="h-4 w-4" />
            <span className="ml-1">
              Photo{line.photos.length > 0 ? ` (${line.photos.length})` : ""}
            </span>
          </Button>
          <Input
            placeholder="Observation…"
            className="min-w-40 flex-1"
            value={line.notes ?? ""}
            onChange={(e) => onChange({ notes: e.target.value })}
          />
        </div>
      ) : line.notes ? (
        <p className="mt-2 text-[13px] text-muted-foreground">{line.notes}</p>
      ) : null}
    </div>
  );
}
