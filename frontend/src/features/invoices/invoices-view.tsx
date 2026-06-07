"use client";

import { useState } from "react";
import Link from "next/link";
import { Upload, FileText, Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { InvoiceUploadDialog } from "./invoice-upload-dialog";
import { EditInvoiceDialog } from "./edit-invoice-dialog";
import { useInvoices, useDeleteInvoice } from "@/hooks/use-invoices";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Invoice } from "@/services/types";

export function InvoicesView() {
  const { data: invoices, isLoading } = useInvoices();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));
  const deleteInvoice = useDeleteInvoice();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [editInvoice, setEditInvoice] = useState<Invoice | null>(null);
  const [toDelete, setToDelete] = useState<Invoice | null>(null);

  const colCount = canWrite ? 6 : 5;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        {canWrite && (
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4" />
            Importer une facture
          </Button>
        )}
      </div>

      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Numéro</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Montant</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead>Importée le</TableHead>
              {canWrite && <TableHead className="text-right pr-6">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: colCount }).map((__, j) => (
                    <TableCell key={j}><Skeleton className="h-5 w-24" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : !invoices || invoices.length === 0 ? (
              <TableRow>
                <TableCell colSpan={colCount}>
                  <div className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground">
                    <FileText className="h-8 w-8" />
                    Aucune facture importée.
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              invoices.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell className="font-medium">
                    <Link href={`/factures/${inv.id}`} className="hover:underline">
                      {inv.invoice_number || "Sans numéro"}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(inv.date)}</TableCell>
                  <TableCell className="tabular-nums">
                    {formatCurrency(inv.total_amount, inv.currency ?? "EUR")}
                  </TableCell>
                  <TableCell><InvoiceStatusBadge invoice={inv} /></TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(inv.created_at)}</TableCell>
                  {canWrite && (
                    <TableCell className="pr-6 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditInvoice(inv)}
                        >
                          <Pencil className="h-4 w-4" />
                          Modifier
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Supprimer la facture"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setToDelete(inv)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <InvoiceUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />

      <EditInvoiceDialog
        open={Boolean(editInvoice)}
        onOpenChange={(o) => !o && setEditInvoice(null)}
        invoice={editInvoice}
      />

      <AlertDialog open={Boolean(toDelete)} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette facture ?</AlertDialogTitle>
            <AlertDialogDescription>
              La facture
              {toDelete?.invoice_number ? ` « ${toDelete.invoice_number} »` : ""}, ses lignes et
              les prix qui en découlent seront supprimés, et les coûts des recettes recalculés.
              Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (toDelete) {
                  deleteInvoice.mutate(toDelete.id, { onSuccess: () => setToDelete(null) });
                }
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
