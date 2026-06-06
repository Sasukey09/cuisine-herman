"use client";

import { useState } from "react";
import Link from "next/link";
import { Upload, FileText } from "lucide-react";

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
import { InvoiceStatusBadge } from "./invoice-status-badge";
import { InvoiceUploadDialog } from "./invoice-upload-dialog";
import { useInvoices } from "@/hooks/use-invoices";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatDate } from "@/lib/utils";

export function InvoicesView() {
  const { data: invoices, isLoading } = useInvoices();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));
  const [uploadOpen, setUploadOpen] = useState(false);

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
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 5 }).map((__, j) => (
                    <TableCell key={j}><Skeleton className="h-5 w-24" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : !invoices || invoices.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5}>
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
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <InvoiceUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}
