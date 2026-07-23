"use client";

import Link from "next/link";
import { Crown } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useProductQuoteHistory } from "@/hooks/use-quotes";
import { formatCurrency, formatDate, formatNumber, cn } from "@/lib/utils";

/** Ce qui a été **proposé**, à côté de ce qui a été **payé** (§10).
 *
 *  Ces prix n'entrent pas dans le food cost — un coût calculé sur un prix jamais
 *  payé serait faux. Mais savoir qu'un fournisseur proposait 18,50 € il y a
 *  trois mois et 21,00 € aujourd'hui est ce qui permet de négocier. */
export function ProductQuoteHistory({ productId }: { productId: string }) {
  const { data, isLoading } = useProductQuoteHistory(productId);
  const offers = data?.offers ?? [];

  if (!isLoading && offers.length === 0) {
    // Pas de bloc vide : sans devis, il n'y a rien à raconter.
    return null;
  }

  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle className="text-base">Devis reçus</CardTitle>
        <CardDescription>
          Les prix proposés pour ce produit — y compris ceux qu&apos;on n&apos;a pas retenus. Ils
          n&apos;entrent pas dans le coût de revient, mais ils servent à négocier.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        {data && offers.length > 0 ? (
          <div className="mb-3 flex flex-wrap gap-x-6 gap-y-1 px-6 text-xs text-muted-foreground">
            <span>
              Meilleure offre{" "}
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                {formatCurrency(data.best_price)}
              </span>
              {data.best_supplier_name ? ` · ${data.best_supplier_name}` : ""}
            </span>
            <span>
              Dernière <span className="font-semibold text-foreground">{formatCurrency(data.latest_price)}</span>
            </span>
            <span>
              Moyenne <span className="font-semibold text-foreground">{formatCurrency(data.avg_price)}</span>
            </span>
            <span>
              {data.count} offre(s) · {data.supplier_count} fournisseur(s)
            </span>
          </div>
        ) : null}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Date</TableHead>
                <TableHead>Fournisseur</TableHead>
                <TableHead>Prix unitaire</TableHead>
                <TableHead>Conditionnement</TableHead>
                <TableHead className="pr-6">Évolution</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading
                ? Array.from({ length: 3 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 5 }).map((__, j) => (
                        <TableCell key={j} className={j === 0 ? "pl-6" : ""}>
                          <Skeleton className="h-5 w-20" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : offers.map((o, i) => (
                    <TableRow key={`${o.quote_id}-${i}`}>
                      <TableCell className="pl-6 text-muted-foreground">
                        {o.date ? formatDate(o.date) : "—"}
                        {o.quote_id ? (
                          <Link
                            href={`/devis/${o.quote_id}`}
                            className="ml-2 text-primary underline underline-offset-4"
                          >
                            {o.quote_number ?? o.quote_reference ?? "devis"}
                          </Link>
                        ) : null}
                      </TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-1.5">
                          {o.supplier_name ?? "—"}
                          {o.is_best ? (
                            <Crown className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                          ) : null}
                        </span>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatCurrency(o.net_unit_price)}
                        {o.discount_pct ? (
                          <span className="ml-1 text-xs text-muted-foreground">
                            (−{formatNumber(o.discount_pct, 1)} %)
                          </span>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {[o.pack_size, o.brand, o.min_qty ? `min. ${formatNumber(o.min_qty, 0)}` : null]
                          .filter(Boolean)
                          .join(" · ") || "—"}
                      </TableCell>
                      <TableCell className="pr-6">
                        {o.delta_pct_vs_previous == null ? (
                          <span className="text-xs text-muted-foreground">—</span>
                        ) : (
                          <Badge
                            variant="outline"
                            className={cn(
                              "tabular-nums",
                              o.delta_pct_vs_previous > 0
                                ? "border-red-500/30 text-red-600 dark:text-red-400"
                                : "border-emerald-500/30 text-emerald-600 dark:text-emerald-400",
                            )}
                          >
                            {o.delta_pct_vs_previous > 0 ? "+" : ""}
                            {formatNumber(o.delta_pct_vs_previous, 1)} %
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
