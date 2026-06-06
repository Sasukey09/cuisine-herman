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
import { useUpdateInvoiceLine } from "@/hooks/use-invoices";
import type { InvoiceLine } from "@/services/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoiceId: string;
  line: InvoiceLine | null;
}

const numOrNull = (s: string) => (s.trim() === "" ? null : Number(s));

export function EditLineDialog({ open, onOpenChange, invoiceId, line }: Props) {
  const update = useUpdateInvoiceLine(invoiceId);
  const [description, setDescription] = useState("");
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("");
  const [unitPrice, setUnitPrice] = useState("");

  useEffect(() => {
    if (line) {
      setDescription(line.description ?? "");
      setQty(line.qty != null ? String(line.qty) : "");
      setUnit("");
      setUnitPrice(line.unit_price != null ? String(line.unit_price) : "");
    }
  }, [line]);

  const save = () => {
    if (!line) return;
    update.mutate(
      {
        lineId: line.id,
        fields: {
          description: description.trim() || undefined,
          qty: numOrNull(qty),
          unit: unit.trim() || undefined,
          unit_price: numOrNull(unitPrice),
        },
      },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Corriger la ligne</DialogTitle>
          <DialogDescription>
            Ajustez les valeurs mal lues par l&apos;OCR. Si la ligne est associée à un
            produit, le prix et les coûts des recettes seront recalculés.
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
          <Button onClick={save} disabled={update.isPending}>
            {update.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
