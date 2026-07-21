"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Plus, Search, Pencil, Trash2, Package } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Input } from "@/components/ui/input";
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
import { ProductFormDialog } from "./product-form-dialog";
import { useEnrichedProducts, useDeleteProduct } from "@/hooks/use-products";
import { useDebounce } from "@/hooks/use-debounce";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency } from "@/lib/utils";
import type { Product, ProductRow } from "@/services/types";

/** Couleurs de famille produit (design FoodGad) — dot devant la catégorie. */
const CATEGORY_COLORS: Record<string, string> = {
  Viande: "#b23a2e",
  Poisson: "#2f6f62",
  Crèmerie: "#d97706",
  Épicerie: "#8a847a",
  Légumes: "#4a7c3f",
};
function categoryColor(c: string) {
  return CATEGORY_COLORS[c] ?? "#8a847a";
}

function Variation({ pct }: { pct?: number | null }) {
  if (pct == null) return <span className="text-muted-foreground">—</span>;
  if (Math.abs(pct) < 0.05) return <Badge variant="secondary">0 %</Badge>;
  const up = pct > 0;
  return (
    <Badge variant={up ? "destructive" : "success"}>
      {up ? "+" : ""}
      {pct.toFixed(1)} %
    </Badge>
  );
}

export function ProductsView() {
  // The header search sends the term here (?q=...): without reading it, that
  // search would navigate and then show an unfiltered list — a dead end.
  const params = useSearchParams();
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [cat, setCat] = useState("");
  const debounced = useDebounce(search, 300);
  const { data: products, isLoading, isError, error, refetch, isFetching } =
    useEnrichedProducts(debounced || undefined);
  const del = useDeleteProduct();
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProductRow | null>(null);

  const categories = useMemo(() => {
    const set = new Set<string>();
    products?.forEach((p) => p.category && set.add(p.category));
    return Array.from(set).sort();
  }, [products]);

  const rows = useMemo(
    () => (products ?? []).filter((p) => !cat || p.category === cat),
    [products, cat],
  );

  const colCount = canWrite ? 7 : 6;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Rechercher un produit…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          className="h-10 rounded-lg border border-input bg-card px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <option value="">Toutes catégories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        {canWrite && (
          <Button variant="gradient" onClick={() => { setEditing(null); setFormOpen(true); }}>
            <Plus className="h-4 w-4" />
            Nouveau produit
          </Button>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-secondary/60 hover:bg-secondary/60">
              <TableHead>Produit</TableHead>
              <TableHead>Catégorie</TableHead>
              <TableHead>Unité</TableHead>
              <TableHead>Dernier coût</TableHead>
              <TableHead>Fournisseur</TableHead>
              <TableHead className="text-right">Variation</TableHead>
              {canWrite && <TableHead className="w-20 text-right pr-6">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isError ? (
              <TableRow>
                <TableCell colSpan={colCount}>
                  <ErrorState error={error} onRetry={() => refetch()} retrying={isFetching} compact />
                </TableCell>
              </TableRow>
            ) : isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: colCount }).map((__, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-5 w-24" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={colCount}>
                  <div className="flex flex-col items-center gap-2 py-12 text-center text-sm text-muted-foreground">
                    <Package className="h-8 w-8" />
                    {debounced || cat ? "Aucun produit ne correspond." : "Aucun produit pour le moment."}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              rows.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-semibold">
                    <Link href={`/produits/${p.id}`} className="hover:underline">
                      {p.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {p.category ? (
                      <span className="inline-flex items-center gap-2">
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ background: categoryColor(p.category) }}
                        />
                        {p.category}
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{p.unit ?? "—"}</TableCell>
                  <TableCell className="font-semibold tabular-nums">
                    {p.last_cost != null ? formatCurrency(p.last_cost, p.currency ?? "EUR") : "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{p.supplier ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <Variation pct={p.variation_pct} />
                  </TableCell>
                  {canWrite && (
                    <TableCell className="pr-6 text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          aria-label="Modifier"
                          onClick={() => {
                            setEditing({ id: p.id, name: p.name, sku: p.sku ?? null });
                            setFormOpen(true);
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          aria-label="Supprimer"
                          onClick={() => setDeleteTarget(p)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
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

      <ProductFormDialog open={formOpen} onOpenChange={setFormOpen} product={editing} />

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce produit ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {deleteTarget?.name} » sera définitivement supprimé. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget)
                  del.mutate(deleteTarget.id, { onSettled: () => setDeleteTarget(null) });
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
