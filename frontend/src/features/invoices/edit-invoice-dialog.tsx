"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUpdateInvoice } from "@/hooks/use-invoices";
import type { Invoice } from "@/services/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoice: Invoice | null;
}

export function EditInvoiceDialog({ open, onOpenChange, invoice }: Props) {
  const update = useUpdateInvoice(invoice?.id ?? "");
  const [number, setNumber] = useState("");
  const [date, setDate] = useState("");
  const [total, setTotal] = useState("");
  const [currency, setCurrency] = useState("");

  useEffect(() => {
    if (open && invoice) {
      setNumber(invoice.invoice_number ?? "");
      setDate(invoice.date ?? "");
      setTotal(invoice.total_amount != null ? String(invoice.total_amount) : "");
      setCurrency(invoice.currency ?? "");
    }
  }, [open, invoice]);

  const save = () => {
    update.mutate(
      {
        invoice_number: number.trim() || undefined,
        date: date.trim() || undefined,
        total_amount: total.trim() === "" ? undefined : Number(total),
        currency: currency.trim() || undefined,
      },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Modifier la facture</DialogTitle>
          <DialogDescription>Corrigez les informations d&apos;en-tête manuellement.</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="ei-num">N° de facture</Label>
            <Input id="ei-num" value={number} onChange={(e) => setNumber(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ei-date">Date</Label>
              <Input id="ei-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ei-cur">Devise</Label>
              <Input id="ei-cur" placeholder="EUR" value={currency} onChange={(e) => setCurrency(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ei-total">Montant total</Label>
            <Input id="ei-total" type="number" value={total} onChange={(e) => setTotal(e.target.value)} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button onClick={save} disabled={update.isPending}>
            {update.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
