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
import { useSuppliers } from "@/hooks/use-suppliers";
import { useAddProductSupplier, useUpdateProductSupplier } from "@/hooks/use-products";
import type { ProductSupplierRow } from "@/services/types";

const SELECT_CLASS =
  "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

interface Props {
  productId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When set, edit that link; otherwise add a new supplier. */
  existing?: ProductSupplierRow | null;
  /** Supplier ids already linked (to hide them in "add" mode). */
  linkedSupplierIds?: string[];
}

export function ProductSupplierDialog({
  productId,
  open,
  onOpenChange,
  existing,
  linkedSupplierIds = [],
}: Props) {
  const isEdit = Boolean(existing?.link_id);
  const { data: suppliers } = useSuppliers();
  const add = useAddProductSupplier(productId);
  const update = useUpdateProductSupplier(productId);

  const [supplierId, setSupplierId] = useState("");
  const [supplierSku, setSupplierSku] = useState("");
  const [packSize, setPackSize] = useState("");
  const [leadTime, setLeadTime] = useState("");
  const [available, setAvailable] = useState(true);
  const [preferred, setPreferred] = useState(false);

  useEffect(() => {
    if (open) {
      setSupplierId(existing?.supplier_id ?? "");
      setSupplierSku(existing?.supplier_sku ?? "");
      setPackSize(existing?.pack_size ?? "");
      setLeadTime(existing?.lead_time_days != null ? String(existing.lead_time_days) : "");
      setAvailable(existing?.available ?? true);
      setPreferred(existing?.preferred ?? false);
    }
  }, [open, existing]);

  const pending = add.isPending || update.isPending;
  const availableSuppliers = (suppliers ?? []).filter(
    (s) => isEdit || !linkedSupplierIds.includes(s.id),
  );

  function onSubmit() {
    const body = {
      supplier_sku: supplierSku.trim() || null,
      pack_size: packSize.trim() || null,
      lead_time_days: leadTime.trim() && !Number.isNaN(Number(leadTime)) ? Number(leadTime) : null,
      available,
      preferred,
    };
    const opts = { onSuccess: () => onOpenChange(false) };
    if (isEdit && existing?.link_id) {
      update.mutate({ linkId: existing.link_id, payload: body }, opts);
    } else {
      if (!supplierId) return;
      add.mutate({ supplier_id: supplierId, ...body }, opts);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Modifier le fournisseur" : "Associer un fournisseur"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? existing?.supplier_name ?? "Fournisseur"
              : "Reliez ce produit à un fournisseur de votre catalogue."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {!isEdit && (
            <div className="space-y-2">
              <Label htmlFor="ps-supplier">Fournisseur</Label>
              <select
                id="ps-supplier"
                className={SELECT_CLASS}
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value)}
              >
                <option value="">Choisir…</option>
                {availableSuppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ps-sku">Référence fournisseur</Label>
              <Input id="ps-sku" value={supplierSku} onChange={(e) => setSupplierSku(e.target.value)} placeholder="SAU-01" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ps-lead">Délai (jours)</Label>
              <Input id="ps-lead" type="number" min={0} value={leadTime} onChange={(e) => setLeadTime(e.target.value)} placeholder="2" />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="ps-pack">Conditionnement</Label>
            <Input id="ps-pack" value={packSize} onChange={(e) => setPackSize(e.target.value)} placeholder="Carton de 6" />
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={available} onChange={(e) => setAvailable(e.target.checked)} />
              Disponible
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={preferred} onChange={(e) => setPreferred(e.target.checked)} />
              Fournisseur préféré
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button type="button" onClick={onSubmit} disabled={pending || (!isEdit && !supplierId)}>
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            {isEdit ? "Enregistrer" : "Associer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
