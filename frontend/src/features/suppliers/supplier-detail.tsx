"use client";

import Link from "next/link";
import { ArrowLeft, Mail, Phone, Hash } from "lucide-react";

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
import { useSupplier, useSupplierPrices } from "@/hooks/use-suppliers";
import { useSupplierPurchaseHistory } from "@/hooks/use-purchasing";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";

export function SupplierDetail({ supplierId }: { supplierId: string }) {
  const { data: supplier, isLoading, isError } = useSupplier(supplierId);
  const { data: prices, isLoading: pricesLoading } = useSupplierPrices(supplierId);
  const { data: purchases } = useSupplierPurchaseHistory(supplierId);

  if (isError) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Fournisseur introuvable.
          <div className="mt-4">
            <Button asChild variant="outline">
              <Link href="/fournisseurs">Retour à la liste</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
        <Link href="/fournisseurs">
          <ArrowLeft className="h-4 w-4" />
          Fournisseurs
        </Link>
      </Button>

      <Card>
        <CardHeader>
          {isLoading || !supplier ? (
            <Skeleton className="h-7 w-48" />
          ) : (
            <>
              <CardTitle className="flex items-center gap-2">
                {supplier.name}
                {supplier.code && <Badge variant="secondary">{supplier.code}</Badge>}
              </CardTitle>
              <CardDescription>Coordonnées et historique tarifaire.</CardDescription>
            </>
          )}
        </CardHeader>
        <CardContent>
          {isLoading || !supplier ? (
            <Skeleton className="h-12 w-full" />
          ) : (
            <div className="flex flex-wrap gap-6 text-sm">
              <span className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-muted-foreground" />
                {supplier.contact?.email || "—"}
              </span>
              <span className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-muted-foreground" />
                {supplier.contact?.phone || "—"}
              </span>
              <span className="flex items-center gap-2">
                <Hash className="h-4 w-4 text-muted-foreground" />
                {supplier.code || "—"}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Historique des achats</CardTitle>
          <CardDescription>Articles achetés chez ce fournisseur (qté, total, coût standardisé, variation).</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Date</TableHead>
                <TableHead>Produit</TableHead>
                <TableHead>Quantité</TableHead>
                <TableHead>Total</TableHead>
                <TableHead className="pr-6">Coût/unité std</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {!purchases || purchases.purchases.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5}>
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      Aucun achat enregistré pour ce fournisseur.
                    </p>
                  </TableCell>
                </TableRow>
              ) : (
                purchases.purchases.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="pl-6 text-muted-foreground">{formatDate(p.purchase_date)}</TableCell>
                    <TableCell className="font-medium">{p.product_name ?? "—"}</TableCell>
                    <TableCell className="tabular-nums">{formatNumber(p.qty)} {p.unit_code ?? ""}</TableCell>
                    <TableCell className="tabular-nums">{formatCurrency(p.total_price, p.currency ?? "EUR")}</TableCell>
                    <TableCell className="pr-6 tabular-nums">
                      {formatCurrency(p.unit_cost_standard, p.currency ?? "EUR")}/{p.unit_code ?? "u"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Historique des prix</CardTitle>
          <CardDescription>Prix relevés sur les factures de ce fournisseur.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Produit</TableHead>
                <TableHead>Prix</TableHead>
                <TableHead>Devise</TableHead>
                <TableHead className="pr-6">Date d&apos;effet</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pricesLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell className="pl-6"><Skeleton className="h-5 w-40" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                    <TableCell className="pr-6"><Skeleton className="h-5 w-24" /></TableCell>
                  </TableRow>
                ))
              ) : !prices || prices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4}>
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      Aucun prix enregistré pour ce fournisseur.
                    </p>
                  </TableCell>
                </TableRow>
              ) : (
                prices.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="pl-6 font-medium">{p.product_name ?? "—"}</TableCell>
                    <TableCell className="tabular-nums">
                      {formatCurrency(p.price, p.currency ?? "EUR")}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{p.currency ?? "—"}</TableCell>
                    <TableCell className="pr-6 text-muted-foreground">
                      {formatDate(p.effective_date)}
                    </TableCell>
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
