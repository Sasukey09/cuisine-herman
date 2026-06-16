"use client";

import Link from "next/link";
import { ArrowLeft, ArrowUpRight, ArrowDownRight, Trophy } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { useProduct } from "@/hooks/use-products";
import { useProductPriceHistory, useSupplierComparison } from "@/hooks/use-purchasing";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";

function Variation({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-muted-foreground">—</span>;
  if (Math.abs(pct) < 0.05) return <span className="text-muted-foreground">0%</span>;
  const up = pct > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`flex items-center gap-1 tabular-nums ${up ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`}>
      <Icon className="h-4 w-4" />
      {up ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

export function ProductDetail({ productId }: { productId: string }) {
  const { data: product, isError } = useProduct(productId);
  const { data: history, isLoading } = useProductPriceHistory(productId);
  const { data: comparison } = useSupplierComparison(productId);

  if (isError) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Produit introuvable.
          <div className="mt-4">
            <Button asChild variant="outline">
              <Link href="/produits">Retour aux produits</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const purchases = [...(history?.purchases ?? [])].reverse(); // newest first for display

  return (
    <div className="space-y-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
        <Link href="/produits">
          <ArrowLeft className="h-4 w-4" />
          Produits
        </Link>
      </Button>

      <Card>
        <CardHeader>
          {!product ? (
            <Skeleton className="h-7 w-48" />
          ) : (
            <>
              <CardTitle className="flex items-center gap-2">
                {product.name}
                {product.sku && <Badge variant="secondary">{product.sku}</Badge>}
              </CardTitle>
              <CardDescription>Historique des achats et comparaison fournisseurs.</CardDescription>
            </>
          )}
        </CardHeader>
      </Card>

      {/* Supplier comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comparaison fournisseurs</CardTitle>
          <CardDescription>Dernier coût standardisé par fournisseur — le moins cher est mis en avant.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {!comparison || comparison.suppliers.length === 0 ? (
            <p className="px-6 py-6 text-sm text-muted-foreground">Aucune donnée d&apos;achat pour comparer.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Fournisseur</TableHead>
                  <TableHead>Coût standardisé</TableHead>
                  <TableHead className="pr-6">Dernier achat</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {comparison.suppliers
                  .slice()
                  .sort((a, b) => (a.unit_cost_standard ?? 1e9) - (b.unit_cost_standard ?? 1e9))
                  .map((s) => (
                    <TableRow key={s.supplier_id ?? "none"} className={s.is_cheapest ? "bg-emerald-500/5" : ""}>
                      <TableCell className="pl-6 font-medium">
                        <span className="flex items-center gap-2">
                          {s.supplier_name ?? "Sans fournisseur"}
                          {s.is_cheapest && (
                            <Badge variant="success" className="gap-1">
                              <Trophy className="h-3 w-3" /> Moins cher
                            </Badge>
                          )}
                        </span>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatCurrency(s.unit_cost_standard, s.currency ?? "EUR")}/{s.unit_code ?? "u"}
                      </TableCell>
                      <TableCell className="pr-6 text-muted-foreground">{formatDate(s.purchase_date)}</TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Purchase history */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Historique des achats</CardTitle>
          <CardDescription>Chaque ligne de facture relevée pour ce produit.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Date</TableHead>
                <TableHead>Fournisseur</TableHead>
                <TableHead>Quantité</TableHead>
                <TableHead>Prix total</TableHead>
                <TableHead>Coût/unité std</TableHead>
                <TableHead className="pr-6">Variation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 6 }).map((__, j) => (
                      <TableCell key={j} className={j === 0 ? "pl-6" : ""}>
                        <Skeleton className="h-5 w-20" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : purchases.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6}>
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      Aucun achat enregistré. Importez des factures contenant ce produit.
                    </p>
                  </TableCell>
                </TableRow>
              ) : (
                purchases.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="pl-6 text-muted-foreground">{formatDate(p.purchase_date)}</TableCell>
                    <TableCell>{p.supplier_name ?? "—"}</TableCell>
                    <TableCell className="tabular-nums">
                      {formatNumber(p.qty)} {p.unit_code ?? ""}
                    </TableCell>
                    <TableCell className="tabular-nums">{formatCurrency(p.total_price, p.currency ?? "EUR")}</TableCell>
                    <TableCell className="tabular-nums">
                      {formatCurrency(p.unit_cost_standard, p.currency ?? "EUR")}/{p.unit_code ?? "u"}
                    </TableCell>
                    <TableCell className="pr-6"><Variation pct={p.variation_pct} /></TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
