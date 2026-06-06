"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Link2, AlertCircle, FileText } from "lucide-react";
import { toast } from "sonner";

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
import { InvoiceStatusBadge } from "./invoice-status-badge";
import { MapProductDialog } from "./map-product-dialog";
import { useInvoice, useInvoiceLines, useProcessInvoice } from "@/hooks/use-invoices";
import { getInvoiceFileUrl } from "@/services/invoices-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { useProducts } from "@/hooks/use-products";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";
import type { InvoiceLine } from "@/services/types";

function MatchCell({
  line,
  productName,
}: {
  line: InvoiceLine;
  productName?: string;
}) {
  if (!line.product_id) {
    return (
      <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
        <AlertCircle className="h-4 w-4" />À revoir
      </span>
    );
  }
  const conf = line.match_confidence ?? 0;
  return (
    <span className="flex items-center gap-2">
      <span className="font-medium">{productName ?? "Produit associé"}</span>
      <Badge variant={conf >= 80 ? "success" : "warning"}>{Math.round(conf)}%</Badge>
    </span>
  );
}

export function InvoiceDetail({ invoiceId }: { invoiceId: string }) {
  const { data: invoice, isLoading, isError } = useInvoice(invoiceId);
  const { data: lines, isLoading: linesLoading } = useInvoiceLines(invoiceId);
  const { data: products } = useProducts();
  const process = useProcessInvoice(invoiceId);
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));

  const [mapLine, setMapLine] = useState<InvoiceLine | null>(null);

  const openFile = async () => {
    try {
      const url = await getInvoiceFileUrl(invoiceId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      toast.error(getApiErrorMessage(e, "Aucun fichier disponible pour cette facture"));
    }
  };

  const productNames = useMemo(() => {
    const m = new Map<string, string>();
    products?.forEach((p) => m.set(p.id, p.name));
    return m;
  }, [products]);

  const needsReview = (lines ?? []).filter((l) => !l.product_id).length;

  if (isError) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Facture introuvable.
          <div className="mt-4">
            <Button asChild variant="outline">
              <Link href="/factures">Retour à l&apos;historique</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
        <Link href="/factures">
          <ArrowLeft className="h-4 w-4" />
          Factures
        </Link>
      </Button>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            {isLoading || !invoice ? (
              <Skeleton className="h-7 w-48" />
            ) : (
              <>
                <CardTitle className="flex items-center gap-2">
                  {invoice.invoice_number || "Facture sans numéro"}
                  <InvoiceStatusBadge invoice={invoice} />
                </CardTitle>
                <CardDescription>
                  {formatDate(invoice.date)} · {formatCurrency(invoice.total_amount, invoice.currency ?? "EUR")}
                </CardDescription>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={openFile}>
              <FileText className="h-4 w-4" />
              Voir le fichier
            </Button>
            {canWrite && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => process.mutate()}
                disabled={process.isPending}
              >
                <RefreshCw className={`h-4 w-4 ${process.isPending ? "animate-spin" : ""}`} />
                Re-traiter
              </Button>
            )}
          </div>
        </CardHeader>
        {needsReview > 0 && (
          <CardContent>
            <div className="flex items-center gap-2 rounded-md bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
              <AlertCircle className="h-4 w-4" />
              {needsReview} ligne(s) à associer manuellement à un produit.
            </div>
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lignes de la facture</CardTitle>
          <CardDescription>Vérifiez et corrigez les associations produit.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Description</TableHead>
                <TableHead>Qté</TableHead>
                <TableHead>PU</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Produit</TableHead>
                {canWrite && <TableHead className="pr-6 text-right">Action</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {linesLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: canWrite ? 6 : 5 }).map((__, j) => (
                      <TableCell key={j} className={j === 0 ? "pl-6" : ""}>
                        <Skeleton className="h-5 w-20" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : !lines || lines.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={canWrite ? 6 : 5}>
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      Aucune ligne extraite.
                    </p>
                  </TableCell>
                </TableRow>
              ) : (
                lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell className="pl-6 font-medium">{line.description ?? "—"}</TableCell>
                    <TableCell className="tabular-nums">{formatNumber(line.qty)}</TableCell>
                    <TableCell className="tabular-nums">{formatCurrency(line.unit_price)}</TableCell>
                    <TableCell className="tabular-nums">{formatCurrency(line.line_total)}</TableCell>
                    <TableCell>
                      <MatchCell
                        line={line}
                        productName={line.product_id ? productNames.get(line.product_id) : undefined}
                      />
                    </TableCell>
                    {canWrite && (
                      <TableCell className="pr-6 text-right">
                        <Button variant="ghost" size="sm" onClick={() => setMapLine(line)}>
                          <Link2 className="h-4 w-4" />
                          {line.product_id ? "Modifier" : "Associer"}
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <MapProductDialog
        open={Boolean(mapLine)}
        onOpenChange={(o) => !o && setMapLine(null)}
        invoiceId={invoiceId}
        line={mapLine}
      />
    </div>
  );
}
