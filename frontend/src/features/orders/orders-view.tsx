"use client";

import { useState } from "react";
import Link from "next/link";
import { Truck, PackageCheck, ClipboardList } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOrders, useOrderStatuses } from "@/hooks/use-orders";
import { formatCurrency, formatDate, cn } from "@/lib/utils";
import type { OrderStatus } from "@/services/types";

/** Le ton d'un état : ce qui attend une action de notre côté ressort. */
function statusTone(status?: OrderStatus | null) {
  switch (status) {
    case "draft":
      return "bg-muted text-muted-foreground";
    case "sent":
    case "confirmed":
    case "preparing":
    case "shipped":
      return "bg-primary/10 text-primary";
    case "partially_received":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
    case "received":
    case "invoiced":
      return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
    case "cancelled":
      return "bg-red-500/10 text-red-700 dark:text-red-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function OrdersView() {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const { data: orders, isLoading } = useOrders(status);
  const { data: statuses } = useOrderStatuses();

  const openCount = (orders ?? []).filter(
    (o) => o.status && !["closed", "cancelled"].includes(o.status),
  ).length;

  return (
    <>
      <PageHeader
        title="Commandes"
        description="Ce qui est engagé auprès des fournisseurs, de l'envoi à la réception."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          onClick={() => setStatus(undefined)}
          className={cn(
            "rounded-full border px-3 py-1 text-[13px] transition-colors",
            status === undefined
              ? "border-primary bg-primary/10 text-primary"
              : "border-border/60 text-muted-foreground hover:border-border",
          )}
        >
          Toutes {orders ? `(${orders.length})` : ""}
        </button>
        {statuses?.map((s) => (
          <button
            key={s.value}
            onClick={() => setStatus(s.value)}
            className={cn(
              "rounded-full border px-3 py-1 text-[13px] transition-colors",
              status === s.value
                ? "border-primary bg-primary/10 text-primary"
                : "border-border/60 text-muted-foreground hover:border-border",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : !orders || orders.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            <ClipboardList className="mx-auto mb-3 h-8 w-8 opacity-40" />
            Aucune commande{status ? " dans cet état" : ""}.{" "}
            <Link
              href="/devis/comparatif"
              className="text-primary underline underline-offset-4"
            >
              Comparez vos devis
            </Link>{" "}
            et commandez les meilleures offres.
          </CardContent>
        </Card>
      ) : (
        <>
          {openCount > 0 && !status ? (
            <p className="mb-3 text-[13px] text-muted-foreground">
              {openCount} commande(s) en cours.
            </p>
          ) : null}
          <div className="space-y-2">
            {orders.map((o) => (
              <Link key={o.id} href={`/commandes/${o.id}`} className="block">
                <Card className="transition-colors hover:border-primary/40">
                  <CardContent className="flex flex-wrap items-center gap-x-4 gap-y-2 py-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{o.reference ?? "Commande"}</span>
                        <Badge className={cn("border-0", statusTone(o.status))}>
                          {o.status_label ?? o.status}
                        </Badge>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-[13px] text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Truck className="h-3.5 w-3.5" />
                          {o.supplier_name ?? "Fournisseur"}
                        </span>
                        <span>{o.line_count} ligne(s)</span>
                        {o.expected_date ? (
                          <span className="inline-flex items-center gap-1">
                            <PackageCheck className="h-3.5 w-3.5" />
                            attendue le {formatDate(o.expected_date)}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold tabular-nums">
                        {formatCurrency(o.total_amount)}
                      </div>
                      {o.delivery_fee ? (
                        <div className="text-[11.5px] text-amber-600 dark:text-amber-400">
                          dont {formatCurrency(o.delivery_fee)} de port
                        </div>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  );
}
