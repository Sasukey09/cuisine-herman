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
import { useUpdateInvoiceLine, useAddInvoiceLine } from "@/hooks/use-invoices";
import type { InvoiceLine } from "@/services/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoiceId: string;
  /** null => create a new line, otherwise edit the given line */
  line: InvoiceLine | null;
}

const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));

export function EditLineDialog({ open, onOpenChange, invoiceId, line }: Props) {
  const isCreate = line === null;
  const update = useUpdateInvoiceLine(invoiceId);
  const add = useAddInvoiceLine(invoiceId);
  const pending = update.isPending || add.isPending;

  const [description, setDescription] = useState("");
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("");
  const [unitPrice, setUnitPrice] = useState("");

  useEffect(() => {
    if (open) {
      setDescription(line?.description ?? "");
      setQty(line?.qty != null ? String(line.qty) : "");
      setUnit("");
      setUnitPrice(line?.unit_price != null ? String(line.unit_price) : "");
    }
  }, [open, line]);

  const save = () => {
    const fields = {
      description: description.trim() || undefined,
      qty: numOrNull(qty),
      unit: unit.trim() || undefined,
      unit_price: numOrNull(unitPrice),
    };
    const onSuccess = () => onOpenChange(false);
    if (isCreate) {
      add.mutate(fields, { onSuccess });
    } else {
      update.mutate({ lineId: line!.id, fields }, { onSuccess });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isCreate ? "Ajouter une ligne" : "Corriger la ligne"}</DialogTitle>
          <DialogDescription>
            {isCreate
              ? "Saisissez une ligne manuellement (utile si l'OCR a raté un article)."
              : "Ajustez les valeurs mal lues. Si la ligne est associée à un produit, le prix et les coûts des recettes seront recalculés."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="el-desc">Description</Label>
            <Input id="el-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="el-qty">Quantité</Label>
              <Input id="el-qty" type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="el-unit">Unité</Label>
              <Input id="el-unit" placeholder="kg, g, l…" value={unit} onChange={(e) => setUnit(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="el-pu">Prix unitaire</Label>
              <Input id="el-pu" type="number" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button onClick={save} disabled={pending}>
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            {isCreate ? "Ajouter" : "Enregistrer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
