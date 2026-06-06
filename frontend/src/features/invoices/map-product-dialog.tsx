"use client";

import { useState } from "react";
import { Search, Check, Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useProducts } from "@/hooks/use-products";
import { useDebounce } from "@/hooks/use-debounce";
import { useMapLineProduct } from "@/hooks/use-invoices";
import type { InvoiceLine } from "@/services/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoiceId: string;
  line: InvoiceLine | null;
}

export function MapProductDialog({ open, onOpenChange, invoiceId, line }: Props) {
  const [search, setSearch] = useState("");
  const debounced = useDebounce(search, 300);
  const { data: products, isLoading } = useProducts(debounced || undefined);
  const map = useMapLineProduct(invoiceId);

  const assign = (productId: string) => {
    if (!line) return;
    map.mutate(
      { lineId: line.id, productId },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Associer un produit</DialogTitle>
          <DialogDescription className="truncate">
            Ligne : « {line?.description ?? "—"} »
          </DialogDescription>
        </DialogHeader>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            autoFocus
            placeholder="Rechercher un produit…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="max-h-72 space-y-1 overflow-y-auto">
          {isLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
          ) : !products || products.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Aucun produit. Créez-en d&apos;abord dans « Produits ».
            </p>
          ) : (
            products.map((p) => {
              const current = p.id === line?.product_id;
              return (
                <button
                  key={p.id}
                  type="button"
                  disabled={map.isPending}
                  onClick={() => assign(p.id)}
                  className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    <span className="font-medium">{p.name}</span>
                    {p.sku && <Badge variant="secondary">{p.sku}</Badge>}
                  </span>
                  {map.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : current ? (
                    <Check className="h-4 w-4 text-primary" />
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
