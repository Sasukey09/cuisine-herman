"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ShoppingCart, Truck } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useCreateOrders, usePlanOrders } from "@/hooks/use-orders";
import { formatCurrency, formatNumber } from "@/lib/utils";
import type { OrderPlan } from "@/services/types";

/** « Commander le moins cher » : l'aperçu, puis l'engagement.
 *
 *  Le comparateur désigne le meilleur prix **produit par produit** — donc
 *  souvent chez plusieurs fournisseurs. Ce dialogue montre ce que ça donne
 *  concrètement (une commande par fournisseur, avec son port et son total)
 *  avant d'engager quoi que ce soit. Découvrir après coup qu'on s'est trompé
 *  de lignes coûterait trois annulations. */
export function OrderFromComparisonDialog({
  open,
  onOpenChange,
  quoteLineIds,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  quoteLineIds: string[];
}) {
  const router = useRouter();
  const plan = usePlanOrders();
  const create = useCreateOrders();
  const [expected, setExpected] = useState("");
  const [plans, setPlans] = useState<OrderPlan[] | null>(null);

  useEffect(() => {
    if (!open || quoteLineIds.length === 0) return;
    setPlans(null);
    plan.mutate(quoteLineIds, { onSuccess: setPlans });
    // `plan` est une mutation stable de React Query ; la relancer à chaque
    // rendu bouclerait.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, quoteLineIds.join(",")]);

  const total = (plans ?? []).reduce((s, p) => s + p.total_amount, 0);

  function confirm(status: "draft" | "sent") {
    create.mutate(
      {
        quote_line_ids: quoteLineIds,
        expected_date: expected || null,
        status,
      },
      {
        onSuccess: (res) => {
          onOpenChange(false);
          // Une seule commande : on l'ouvre. Plusieurs : la liste, sinon on
          // choisirait arbitrairement laquelle montrer.
          router.push(
            res.order_count === 1 ? `/commandes/${res.orders[0].id}` : "/commandes",
          );
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            Commander les meilleures offres
          </DialogTitle>
          <DialogDescription>
            {quoteLineIds.length} offre(s) retenue(s). Le panier est réparti entre les
            fournisseurs qui les proposent — une commande par fournisseur.
          </DialogDescription>
        </DialogHeader>

        {plan.isPending || plans === null ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Calcul de la répartition…
          </div>
        ) : plans.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Aucune offre exploitable dans cette sélection.
          </p>
        ) : (
          <div className="space-y-3">
            {plans.map((p, i) => (
              <div key={p.supplier_id ?? i} className="rounded-lg border border-border/60 p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-semibold">{p.supplier_name ?? "Fournisseur"}</span>
                  <span className="tabular-nums font-semibold">
                    {formatCurrency(p.total_amount)}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <Badge variant="secondary">{p.lines.length} ligne(s)</Badge>
                  <span>panier {formatCurrency(p.lines_total)}</span>
                  {p.delivery_fee ? (
                    <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                      <Truck className="h-3 w-3" />+{formatCurrency(p.delivery_fee)} de port
                    </span>
                  ) : null}
                  {p.discount_total ? (
                    <span className="text-emerald-600 dark:text-emerald-400">
                      −{formatCurrency(p.discount_total)} de remise
                    </span>
                  ) : null}
                </div>
                <ul className="mt-2 space-y-0.5 text-[13px]">
                  {p.lines.map((l, j) => (
                    <li key={j} className="flex justify-between gap-3">
                      <span className="truncate text-muted-foreground">
                        {l.description ?? "Ligne"}
                        {l.qty_ordered ? ` × ${formatNumber(l.qty_ordered, 0)}` : ""}
                      </span>
                      <span className="tabular-nums">{formatCurrency(l.line_total)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}

            <div className="flex items-baseline justify-between border-t border-border/60 pt-3 text-sm">
              <span className="font-semibold">
                Total engagé · {plans.length} commande(s)
              </span>
              <span className="text-base font-bold tabular-nums">{formatCurrency(total)}</span>
            </div>

            <div className="space-y-1">
              <Label htmlFor="of-expected">Livraison souhaitée</Label>
              <Input
                id="of-expected"
                type="date"
                value={expected}
                onChange={(e) => setExpected(e.target.value)}
              />
            </div>
          </div>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <div className="flex gap-2">
            {/* Deux sorties : relire avant d'engager, ou engager tout de suite.
                Le défaut visuel reste le brouillon — l'action irréversible ne
                doit pas être celle qu'on clique sans y penser. */}
            <Button
              variant="outline"
              disabled={create.isPending || !plans?.length}
              onClick={() => confirm("draft")}
            >
              Créer en brouillon
            </Button>
            <Button
              disabled={create.isPending || !plans?.length}
              onClick={() => confirm("sent")}
            >
              {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              <span className={create.isPending ? "ml-2" : ""}>Commander</span>
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
