"use client";

import Link from "next/link";
import { Trash2, Truck, FileText, PackageCheck } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { BackButton } from "@/components/back-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuthStore } from "@/stores/auth-store";
import { useReceipts } from "@/hooks/use-receipts";
import {
  useDeleteOrder,
  useOrder,
  useOrderStatuses,
  useUpdateOrder,
} from "@/hooks/use-orders";
import { formatCurrency, formatDate, formatNumber, cn } from "@/lib/utils";

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

export function OrderDetail({ orderId }: { orderId: string }) {
  const { data: order, isLoading } = useOrder(orderId);
  const { data: statuses } = useOrderStatuses();
  const update = useUpdateOrder();
  const remove = useDeleteOrder();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));
  const { data: receipts } = useReceipts({ order_id: orderId });

  if (isLoading) {
    return (
      <>
        <BackButton fallbackHref="/commandes" />
        <Skeleton className="h-40 w-full" />
      </>
    );
  }
  if (!order) {
    return (
      <>
        <BackButton fallbackHref="/commandes" />
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Commande introuvable.
          </CardContent>
        </Card>
      </>
    );
  }

  // Une commande déjà engagée ne se supprime pas : elle s'annule. Masquer le
  // bouton vaut mieux que de laisser cliquer pour récolter un 409.
  const deletable = order.status === "draft" || order.status === "cancelled";
  const anyReceived = order.lines.some((l) => (l.qty_received ?? 0) > 0);

  return (
    <>
      <BackButton fallbackHref="/commandes" />
      <PageHeader
        title={order.reference ?? "Commande"}
        description={`${order.supplier_name ?? "Fournisseur"} · ${order.line_count} ligne(s)`}
      />

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-3 py-5">
          <div>
            <div className="text-[11.5px] uppercase tracking-wide text-muted-foreground">
              État
            </div>
            {canWrite ? (
              <select
                className={cn(SELECT_CLASS, "mt-1")}
                value={order.status ?? "draft"}
                onChange={(e) =>
                  update.mutate({ id: order.id, status: e.target.value })
                }
                aria-label="État de la commande"
              >
                {statuses?.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            ) : (
              <Badge className="mt-1">{order.status_label}</Badge>
            )}
          </div>
          <div>
            <div className="text-[11.5px] uppercase tracking-wide text-muted-foreground">
              Total engagé
            </div>
            <div className="text-lg font-bold tabular-nums">
              {formatCurrency(order.total_amount)}
            </div>
          </div>
          {order.delivery_fee ? (
            <div>
              <div className="text-[11.5px] uppercase tracking-wide text-muted-foreground">
                Port
              </div>
              <div className="inline-flex items-center gap-1 font-semibold text-amber-600 dark:text-amber-400">
                <Truck className="h-4 w-4" />
                {formatCurrency(order.delivery_fee)}
              </div>
            </div>
          ) : null}
          {order.expected_date ? (
            <div>
              <div className="text-[11.5px] uppercase tracking-wide text-muted-foreground">
                Livraison attendue
              </div>
              <div className="font-semibold">{formatDate(order.expected_date)}</div>
            </div>
          ) : null}
          {order.ordered_at ? (
            <div>
              <div className="text-[11.5px] uppercase tracking-wide text-muted-foreground">
                Commandée le
              </div>
              <div className="font-semibold">{formatDate(order.ordered_at)}</div>
            </div>
          ) : null}

          {/* Réceptionner : l'action principale d'une commande engagée. Elle
              n'a pas de sens sur un brouillon — on ne reçoit pas ce qu'on n'a
              pas commandé. */}
          {canWrite && order.status !== "draft" && order.status !== "cancelled" ? (
            <Button asChild size="sm" className="ml-auto">
              <Link href={`/commandes/${order.id}/reception`}>
                <PackageCheck className="h-4 w-4" />
                <span className="ml-1">Réceptionner</span>
              </Link>
            </Button>
          ) : null}

          {canWrite && deletable ? (
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto text-muted-foreground"
              onClick={() => remove.mutate(order.id)}
            >
              <Trash2 className="h-4 w-4" />
              <span className="ml-1">Supprimer</span>
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {order.conditions ? (
        <p className="mb-4 text-[13px] text-muted-foreground">
          <span className="font-medium text-foreground">Conditions :</span>{" "}
          {order.conditions}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lignes commandées</CardTitle>
          <CardDescription>
            Les prix sont ceux du devis retenu. Le reçu se lit dans les réceptions —
            aucun compteur n&apos;est tenu ici.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Produit</TableHead>
                  <TableHead>Commandé</TableHead>
                  {anyReceived ? <TableHead>Reçu</TableHead> : null}
                  <TableHead>PU</TableHead>
                  <TableHead className="pr-6">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.lines.map((l) => {
                  const short = (l.qty_received ?? 0) < (l.qty_ordered ?? 0);
                  return (
                    <TableRow key={l.id}>
                      <TableCell className="pl-6">
                        {l.product_id ? (
                          <Link
                            href={`/produits/${l.product_id}`}
                            className="hover:underline"
                          >
                            {l.product_name ?? l.description}
                          </Link>
                        ) : (
                          (l.description ?? "Ligne")
                        )}
                        {l.pack_size || l.brand ? (
                          <div className="text-[11.5px] text-muted-foreground">
                            {[l.pack_size, l.brand].filter(Boolean).join(" · ")}
                          </div>
                        ) : null}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatNumber(l.qty_ordered, 0)}
                      </TableCell>
                      {anyReceived ? (
                        <TableCell
                          className={cn(
                            "tabular-nums",
                            short && "text-amber-600 dark:text-amber-400",
                          )}
                        >
                          {formatNumber(l.qty_received ?? 0, 0)}
                        </TableCell>
                      ) : null}
                      <TableCell className="tabular-nums">
                        {formatCurrency(l.unit_price)}
                      </TableCell>
                      <TableCell className="pr-6 tabular-nums font-medium">
                        {formatCurrency(l.line_total)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {receipts && receipts.length > 0 ? (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">Réceptions</CardTitle>
            <CardDescription>
              Une commande peut être livrée en plusieurs fois. Chaque réception reste
              au dossier, y compris celles qui ont été refusées.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {receipts.map((r) => (
              <Link
                key={r.id}
                href={`/receptions/${r.id}`}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border/60 px-3 py-2 text-sm transition-colors hover:border-primary/40"
              >
                <span className="font-medium">{r.reference}</span>
                <Badge variant="outline">{r.status_label}</Badge>
                {r.received_at ? (
                  <span className="text-muted-foreground">{formatDate(r.received_at)}</span>
                ) : null}
                <span className="text-muted-foreground">{r.line_count} ligne(s)</span>
                {r.received_by_name ? (
                  <span className="ml-auto text-[12.5px] text-muted-foreground">
                    par {r.received_by_name}
                  </span>
                ) : null}
              </Link>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {order.lines.some((l) => l.source_quote_line_id) ? (
        <p className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] text-muted-foreground">
          <FileText className="h-3.5 w-3.5" />
          Les prix de cette commande viennent des devis comparés : ils n&apos;ont pas été
          recalculés depuis l&apos;historique d&apos;achat.
        </p>
      ) : null}
    </>
  );
}
