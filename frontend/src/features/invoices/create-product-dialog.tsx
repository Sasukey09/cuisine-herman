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
import { useCreateProductFromLine } from "@/hooks/use-invoices";
import type { InvoiceLine } from "@/services/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoiceId: string;
  line: InvoiceLine | null;
}

export function CreateProductDialog({ open, onOpenChange, invoiceId, line }: Props) {
  const create = useCreateProductFromLine(invoiceId);
  const [name, setName] = useState("");
  const [sku, setSku] = useState("");

  useEffect(() => {
    if (open) {
      setName(line?.description ?? "");
      setSku("");
    }
  }, [open, line]);

  const save = () => {
    if (!line) return;
    create.mutate(
      { lineId: line.id, name: name.trim() || undefined, sku: sku.trim() || undefined },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Créer le produit</DialogTitle>
          <DialogDescription>
            Crée un nouveau produit du catalogue à partir de cette ligne, l&apos;associe
            automatiquement et calcule son prix.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="cp-name">Nom du produit</Label>
            <Input id="cp-name" value={name} onChange={(e) => setName(e.target.value)} />
            <p className="text-xs text-muted-foreground">
              Conseil : un nom court et générique (ex. « Tomate ») s&apos;associera mieux aux
              prochaines factures.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cp-sku">Référence / SKU (optionnel)</Label>
            <Input id="cp-sku" value={sku} onChange={(e) => setSku(e.target.value)} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button onClick={save} disabled={create.isPending || !name.trim()}>
            {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Créer et associer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
