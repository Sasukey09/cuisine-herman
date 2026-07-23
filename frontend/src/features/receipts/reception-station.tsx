"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, PackageCheck } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { BackButton } from "@/components/back-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useCreateReceipt,
  useQualityVocabulary,
  useReceiptPrefill,
  useValidateReceipt,
} from "@/hooks/use-receipts";
import { formatCurrency, formatNumber } from "@/lib/utils";
import type { ReceiptLine } from "@/services/types";
import { ReceptionLineCard, lineTotals } from "./reception-line-card";

/** Le poste de réception d'une commande.
 *
 *  Un réceptionnaire ne valide pas des quantités : il contrôle une livraison.
 *  L'écran est donc construit autour de la ligne — ce qui est arrivé, ce qu'on
 *  en accepte, et pourquoi — plutôt qu'autour d'un formulaire de saisie. */
export function ReceptionStation({ orderId }: { orderId: string }) {
  const router = useRouter();
  const { data: prefill, isLoading } = useReceiptPrefill(orderId);
  const { data: vocabulary } = useQualityVocabulary();
  const create = useCreateReceipt();
  const validate = useValidateReceipt();

  const [lines, setLines] = useState<ReceiptLine[]>([]);
  const [receivedAt, setReceivedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [deliveryNote, setDeliveryNote] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!prefill) return;
    setLines(
      prefill.lines.map((l) => ({
        order_line_id: l.order_line_id,
        product_id: l.product_id,
        product_name: l.description,
        description: l.description,
        // Pré-rempli avec ce qui RESTE dû : proposer la quantité commandée
        // re-proposerait du déjà reçu dès la deuxième livraison.
        qty_delivered: l.qty_delivered ?? null,
        unit_id: l.unit_id,
        unit_price: l.unit_price,
        pack_size: l.pack_size,
        issues: [],
        photos: [],
      })),
    );
  }, [prefill]);

  function patchLine(index: number, patch: Partial<ReceiptLine>) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  const totals = lines.map(lineTotals);
  const anomalies = lines.reduce((n, l) => n + l.issues.length, 0);
  const missing = prefill
    ? prefill.lines.reduce((sum, l, i) => {
        const due = (l.qty_ordered ?? 0) - l.qty_already_received - (totals[i]?.accepted ?? 0);
        return sum + (due > 0 ? due * (l.unit_price ?? 0) : 0);
      }, 0)
    : 0;

  async function save(thenValidate: boolean) {
    const receipt = await create.mutateAsync({
      order_id: orderId,
      supplier_id: prefill?.supplier_id ?? null,
      received_at: receivedAt || null,
      delivery_note_number: deliveryNote || null,
      notes: notes || null,
      // L'appareil de saisie : un poste en bureau et un téléphone en chambre
      // froide n'expliquent pas de la même façon une saisie douteuse.
      device_info: typeof navigator !== "undefined" ? `Web · ${navigator.platform}` : "Web",
      lines,
    });
    if (thenValidate) {
      await validate.mutateAsync(receipt.id);
    }
    router.push(`/receptions/${receipt.id}`);
  }

  if (isLoading) {
    return (
      <>
        <BackButton fallbackHref={`/commandes/${orderId}`} />
        <p className="text-sm text-muted-foreground">Chargement de la commande…</p>
      </>
    );
  }

  if (!prefill || prefill.lines.length === 0) {
    return (
      <>
        <BackButton fallbackHref={`/commandes/${orderId}`} />
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Cette commande n&apos;a plus rien à recevoir.
          </CardContent>
        </Card>
      </>
    );
  }

  const busy = create.isPending || validate.isPending;

  return (
    <>
      <BackButton fallbackHref={`/commandes/${orderId}`} />
      <PageHeader
        title="Réception de marchandise"
        description={`Commande ${prefill.order_reference ?? ""} — contrôlez les quantités et l'état de la livraison.`}
      />

      <Card className="mb-4">
        <CardContent className="flex flex-wrap gap-4 py-4">
          <div className="space-y-1">
            <Label htmlFor="rc-date">Date de réception</Label>
            <Input
              id="rc-date"
              type="date"
              value={receivedAt}
              onChange={(e) => setReceivedAt(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="rc-bl">N° de bon de livraison</Label>
            <Input
              id="rc-bl"
              value={deliveryNote}
              onChange={(e) => setDeliveryNote(e.target.value)}
              placeholder="BL-2026-…"
            />
          </div>
          <div className="min-w-52 flex-1 space-y-1">
            <Label htmlFor="rc-notes">Observations</Label>
            <Input
              id="rc-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Camion en retard, chauffeur pressé…"
            />
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {lines.map((line, i) => (
          <ReceptionLineCard
            key={line.order_line_id ?? i}
            line={line}
            ordered={prefill.lines[i]?.qty_ordered}
            alreadyReceived={prefill.lines[i]?.qty_already_received}
            vocabulary={vocabulary}
            onChange={(patch) => patchLine(i, patch)}
          />
        ))}
      </div>

      <div className="sticky bottom-0 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/60 bg-card/95 px-4 py-3 backdrop-blur">
        <div className="text-[13.5px] text-muted-foreground">
          <span className="font-semibold text-foreground">
            {formatNumber(totals.reduce((n, t) => n + t.accepted, 0), 0)}
          </span>{" "}
          accepté(s)
          {anomalies > 0 ? (
            <>
              {" "}·{" "}
              <span className="text-amber-600 dark:text-amber-400">
                {anomalies} anomalie(s)
              </span>
            </>
          ) : null}
          {missing > 0.005 ? (
            <>
              {" "}·{" "}
              <span className="text-red-600 dark:text-red-400">
                {formatCurrency(missing)} manquants
              </span>
            </>
          ) : null}
        </div>
        <div className="flex gap-2">
          {/* Deux sorties. Le brouillon se corrige ; la validation fige la
              réception et fait entrer l'accepté en stock. */}
          <Button variant="outline" disabled={busy} onClick={() => save(false)}>
            Enregistrer le brouillon
          </Button>
          <Button disabled={busy} onClick={() => save(true)}>
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            <span className="ml-2">Valider la réception</span>
          </Button>
        </div>
      </div>

      <p className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] text-muted-foreground">
        <PackageCheck className="h-3.5 w-3.5" />
        Une réception validée ne se modifie plus. Pour corriger, enregistrez une
        nouvelle réception.
      </p>
    </>
  );
}
