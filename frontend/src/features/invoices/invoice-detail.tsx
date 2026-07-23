"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Link2, AlertCircle, FileText, Pencil, Trash2, Plus, PackagePlus } from "lucide-react";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { InvoiceStatusBadge } from "./invoice-status-badge";
import { MapProductDialog } from "./map-product-dialog";
import { EditLineDialog } from "./edit-line-dialog";
import { EditInvoiceDialog } from "./edit-invoice-dialog";
import { CreateProductDialog } from "./create-product-dialog";
import {
  useInvoice,
  useInvoiceLines,
  useProcessInvoice,
  useDeleteInvoice,
  useDeleteInvoiceLine,
} from "@/hooks/use-invoices";
import { getInvoiceFileUrl } from "@/services/invoices-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { useProducts } from "@/hooks/use-products";
import { InvoiceControlCard } from "./invoice-control-card";
import { SafeBoundary } from "@/components/safe-boundary";
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
  const deleteInvoice = useDeleteInvoice();
  const deleteLine = useDeleteInvoiceLine(invoiceId);
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));
  const router = useRouter();

  const [mapLine, setMapLine] = useState<InvoiceLine | null>(null);
  const [lineDialog, setLineDialog] = useState<{ open: boolean; line: InvoiceLine | null }>({
    open: false,
    line: null,
  });
  const [editInvoiceOpen, setEditInvoiceOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [createProductLine, setCreateProductLine] = useState<InvoiceLine | null>(null);

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
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => process.mutate()}
                  disabled={process.isPending}
                >
                  <RefreshCw className={`h-4 w-4 ${process.isPending ? "animate-spin" : ""}`} />
                  Re-traiter
                </Button>
                <Button variant="outline" size="sm" onClick={() => setEditInvoiceOpen(true)}>
                  <Pencil className="h-4 w-4" />
                  Modifier
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => setDeleteOpen(true)}
                >
                  <Trash2 className="h-4 w-4" />
                  Supprimer
                </Button>
              </>
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

      {/* Contrôle prévu / facturé — ne s'affiche que si un devis est rattaché. */}
      <SafeBoundary>
        <InvoiceControlCard invoiceId={invoiceId} />
      </SafeBoundary>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">Lignes de la facture</CardTitle>
            <CardDescription>Vérifiez, corrigez ou ajoutez des lignes.</CardDescription>
          </div>
          {canWrite && (
            <Button variant="outline" size="sm" onClick={() => setLineDialog({ open: true, line: null })}>
              <Plus className="h-4 w-4" />
              Ajouter une ligne
            </Button>
          )}
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
                        <Button variant="ghost" size="sm" onClick={() => setLineDialog({ open: true, line })}>
                          <Pencil className="h-4 w-4" />
                          Corriger
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setMapLine(line)}>
                          <Link2 className="h-4 w-4" />
                          {line.product_id ? "Produit" : "Associer"}
                        </Button>
                        {!line.product_id && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setCreateProductLine(line)}
                          >
                            <PackagePlus className="h-4 w-4" />
                            Créer produit
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Supprimer la ligne"
                          onClick={() => deleteLine.mutate(line.id)}
                        >
                          <Trash2 className="h-4 w-4" />
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

      <EditLineDialog
        open={lineDialog.open}
        onOpenChange={(o) => setLineDialog((s) => ({ ...s, open: o }))}
        invoiceId={invoiceId}
        line={lineDialog.line}
      />

      <EditInvoiceDialog
        open={editInvoiceOpen}
        onOpenChange={setEditInvoiceOpen}
        invoice={invoice ?? null}
      />

      <CreateProductDialog
        open={Boolean(createProductLine)}
        onOpenChange={(o) => !o && setCreateProductLine(null)}
        invoiceId={invoiceId}
        line={createProductLine}
      />

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette facture ?</AlertDialogTitle>
            <AlertDialogDescription>
              La facture, ses lignes et les prix qui en découlent seront supprimés, et les
              coûts des recettes recalculés. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() =>
                deleteInvoice.mutate(invoiceId, {
                  onSuccess: () => router.push("/factures"),
                })
              }
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
