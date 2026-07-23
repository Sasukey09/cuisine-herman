"use client";

import Link from "next/link";
import { PackageCheck, ShieldCheck } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useReceipts } from "@/hooks/use-receipts";
import { formatDate, cn } from "@/lib/utils";

export function ReceiptsView() {
  const { data: receipts, isLoading } = useReceipts();

  return (
    <>
      <PageHeader
        title="Réceptions"
        description="Ce qui a été livré, ce qui a été accepté, et ce qui a été refusé."
      />

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : !receipts || receipts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            <PackageCheck className="mx-auto mb-3 h-8 w-8 opacity-40" />
            Aucune réception. Elles se créent depuis une{" "}
            <Link href="/commandes" className="text-primary underline underline-offset-4">
              commande
            </Link>
            , à la livraison.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {receipts.map((r) => {
            const frozen = r.status === "checked";
            return (
              <Link key={r.id} href={`/receptions/${r.id}`} className="block">
                <Card className="transition-colors hover:border-primary/40">
                  <CardContent className="flex flex-wrap items-center gap-x-4 gap-y-2 py-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{r.reference ?? "Réception"}</span>
                        <Badge
                          className={cn(
                            "border-0",
                            frozen
                              ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                              : "bg-muted text-muted-foreground",
                          )}
                        >
                          {frozen ? <ShieldCheck className="mr-1 h-3 w-3" /> : null}
                          {r.status_label}
                        </Badge>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-[13px] text-muted-foreground">
                        <span>{r.supplier_name ?? "Fournisseur"}</span>
                        {r.order_reference ? <span>{r.order_reference}</span> : null}
                        <span>{r.line_count} ligne(s)</span>
                        {r.received_at ? <span>{formatDate(r.received_at)}</span> : null}
                      </div>
                    </div>
                    {r.received_by_name ? (
                      <div className="text-right text-[12.5px] text-muted-foreground">
                        par {r.received_by_name}
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
