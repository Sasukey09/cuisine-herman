"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  ArrowDownRight,
  Trophy,
  Star,
  Pencil,
  Trash2,
  Plus,
  ExternalLink,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useProduct,
  useProductSuppliers,
  useProductInvoices,
  useProductRecipes,
  useUpdateProductSupplier,
  useDeleteProductSupplier,
} from "@/hooks/use-products";
import { useProductPriceHistory } from "@/hooks/use-purchasing";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";
import type { ProductSupplierRow } from "@/services/types";
import { ProductFormDialog } from "./product-form-dialog";
import { ProductSupplierDialog } from "./product-supplier-dialog";

function Variation({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-muted-foreground">—</span>;
  if (Math.abs(pct) < 0.05) return <span className="text-muted-foreground">0%</span>;
  const up = pct > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`flex items-center gap-1 tabular-nums ${up ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`}>
      <Icon className="h-4 w-4" />
      {up ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export function ProductDetail({ productId }: { productId: string }) {
  const canWrite = useAuthStore((s) => s.hasRole("admin", "manager"));
  const { data: product, isError } = useProduct(productId);
  const { data: history, isLoading } = useProductPriceHistory(productId);
  const { data: suppliersData } = useProductSuppliers(productId);
  const { data: invoices } = useProductInvoices(productId);
  const { data: recipes } = useProductRecipes(productId);

  const updateSupplier = useUpdateProductSupplier(productId);
  const deleteSupplier = useDeleteProductSupplier(productId);

  const [editOpen, setEditOpen] = useState(false);
  const [supplierDialog, setSupplierDialog] = useState<{ open: boolean; row: ProductSupplierRow | null }>({
    open: false,
    row: null,
  });
  const [deleteLink, setDeleteLink] = useState<ProductSupplierRow | null>(null);

  const purchases = useMemo(() => [...(history?.purchases ?? [])].reverse(), [history]); // newest first
  const chrono = useMemo(() => (history?.purchases ?? []).filter((p) => p.unit_cost_standard != null), [history]);

  const stats = useMemo(() => {
    const costs = chrono.map((p) => p.unit_cost_standard as number);
    if (costs.length === 0) return null;
    const sum = costs.reduce((a, b) => a + b, 0);
    return {
      count: costs.length,
      last: costs[costs.length - 1],
      avg: sum / costs.length,
      min: Math.min(...costs),
      max: Math.max(...costs),
      variation: costs.length > 1 && costs[0] > 0 ? ((costs[costs.length - 1] - costs[0]) / costs[0]) * 100 : null,
      currency: chrono[chrono.length - 1]?.currency ?? "EUR",
      unit: chrono[chrono.length - 1]?.unit_code ?? "u",
    };
  }, [chrono]);

  const suppliers = suppliersData?.suppliers ?? [];
  const linkedIds = suppliers.map((s) => s.supplier_id);

  if (isError) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Produit introuvable.
          <div className="mt-4">
            <Button asChild variant="outline">
              <Link href="/produits">Retour aux produits</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  function setPreferred(row: ProductSupplierRow) {
    if (!row.link_id) return;
    updateSupplier.mutate({ linkId: row.link_id, payload: { preferred: true } });
  }

  return (
    <div className="space-y-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit">
        <Link href="/produits">
          <ArrowLeft className="h-4 w-4" />
          Produits
        </Link>
      </Button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {!product ? (
            <Skeleton className="h-8 w-56" />
          ) : (
            <h1 className="flex items-center gap-2 font-serif text-2xl font-semibold">
              {product.name}
              {product.sku && <Badge variant="secondary">{product.sku}</Badge>}
              {product.category && <Badge variant="outline">{product.category}</Badge>}
            </h1>
          )}
        </div>
        {canWrite && product && (
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            <span className="ml-1">Modifier</span>
          </Button>
        )}
      </div>

      <Tabs defaultValue="infos">
        <TabsList>
          <TabsTrigger value="infos">Informations</TabsTrigger>
          <TabsTrigger value="suppliers">Fournisseurs</TabsTrigger>
          <TabsTrigger value="prices">Historique des prix</TabsTrigger>
          <TabsTrigger value="invoices">Factures</TabsTrigger>
          <TabsTrigger value="recipes">Recettes</TabsTrigger>
          <TabsTrigger value="stats">Statistiques</TabsTrigger>
        </TabsList>

        {/* ---------- Informations ---------- */}
        <TabsContent value="infos">
          <Card>
            <CardContent className="grid gap-4 py-6 sm:grid-cols-2">
              <Field label="Nom" value={product?.name} />
              <Field label="Référence / SKU" value={product?.sku || "—"} />
              <Field label="Catégorie" value={product?.category || "Non classé"} />
              <Field label="Unité de base" value={product?.unit || "—"} />
              <Field label="TVA" value={product?.vat_rate != null ? `${product.vat_rate} %` : "—"} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ---------- Fournisseurs ---------- */}
        <TabsContent value="suppliers">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">Fournisseurs</CardTitle>
                <CardDescription>Prix, disponibilité et délais par fournisseur.</CardDescription>
              </div>
              {canWrite && (
                <Button size="sm" onClick={() => setSupplierDialog({ open: true, row: null })}>
                  <Plus className="h-4 w-4" />
                  <span className="ml-1">Ajouter</span>
                </Button>
              )}
            </CardHeader>
            <CardContent className="px-0">
              {suppliers.length === 0 ? (
                <p className="px-6 py-8 text-center text-sm text-muted-foreground">
                  Aucun fournisseur pour ce produit. Ajoutez-en un ou importez une facture.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="pl-6">Fournisseur</TableHead>
                        <TableHead>Dispo.</TableHead>
                        <TableHead>Réf.</TableHead>
                        <TableHead>Délai</TableHead>
                        <TableHead>Dernier</TableHead>
                        <TableHead>Moyen</TableHead>
                        <TableHead>Meilleur</TableHead>
                        <TableHead>Dernier achat</TableHead>
                        {canWrite && <TableHead className="pr-6 text-right">Actions</TableHead>}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {suppliers.map((s) => (
                        <TableRow key={s.supplier_id} className={s.preferred ? "bg-amber-500/5" : ""}>
                          <TableCell className="pl-6 font-medium">
                            <span className="flex items-center gap-2">
                              {s.preferred && <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-500" />}
                              {s.supplier_name ?? "Sans fournisseur"}
                              {s.is_cheapest && (
                                <Badge variant="success" className="gap-1">
                                  <Trophy className="h-3 w-3" /> Moins cher
                                </Badge>
                              )}
                            </span>
                          </TableCell>
                          <TableCell>
                            {s.available ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                            ) : (
                              <XCircle className="h-4 w-4 text-muted-foreground" />
                            )}
                          </TableCell>
                          <TableCell className="text-muted-foreground">{s.supplier_sku || "—"}</TableCell>
                          <TableCell className="tabular-nums">{s.lead_time_days != null ? `${s.lead_time_days} j` : "—"}</TableCell>
                          <TableCell className="tabular-nums">{s.last_cost != null ? `${formatCurrency(s.last_cost, s.currency ?? "EUR")}/${s.unit_code ?? "u"}` : "—"}</TableCell>
                          <TableCell className="tabular-nums">{s.avg_cost != null ? formatCurrency(s.avg_cost, s.currency ?? "EUR") : "—"}</TableCell>
                          <TableCell className="tabular-nums">{s.best_cost != null ? formatCurrency(s.best_cost, s.currency ?? "EUR") : "—"}</TableCell>
                          <TableCell className="text-muted-foreground">{formatDate(s.last_purchase_date)}</TableCell>
                          {canWrite && (
                            <TableCell className="pr-6">
                              <div className="flex items-center justify-end gap-1">
                                {!s.preferred && (
                                  <Button variant="ghost" size="icon" className="h-7 w-7" title="Définir préféré" onClick={() => setPreferred(s)}>
                                    <Star className="h-3.5 w-3.5" />
                                  </Button>
                                )}
                                <Button variant="ghost" size="icon" className="h-7 w-7" title="Modifier" onClick={() => setSupplierDialog({ open: true, row: s })}>
                                  <Pencil className="h-3.5 w-3.5" />
                                </Button>
                                <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" title="Retirer" onClick={() => setDeleteLink(s)}>
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ---------- Historique des prix ---------- */}
        <TabsContent value="prices">
          {stats && (
            <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Dernier prix" value={`${formatCurrency(stats.last, stats.currency)}/${stats.unit}`} />
              <Stat label="Prix moyen" value={formatCurrency(stats.avg, stats.currency)} />
              <Stat label="Prix minimum" value={formatCurrency(stats.min, stats.currency)} />
              <Stat label="Prix maximum" value={formatCurrency(stats.max, stats.currency)} />
            </div>
          )}
          {chrono.length > 1 && (
            <Card className="mb-4">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Évolution du coût standardisé</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chrono.map((p) => ({ date: formatDate(p.purchase_date), cost: p.unit_cost_standard }))}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} width={48} />
                      <RTooltip />
                      <Line type="monotone" dataKey="cost" stroke="#c2410c" strokeWidth={2} dot={{ r: 2 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Historique des achats</CardTitle>
              <CardDescription>Chaque ligne de facture relevée pour ce produit.</CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-6">Date</TableHead>
                      <TableHead>Fournisseur</TableHead>
                      <TableHead>Quantité</TableHead>
                      <TableHead>Prix total</TableHead>
                      <TableHead>Coût/unité std</TableHead>
                      <TableHead className="pr-6">Variation</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {isLoading ? (
                      Array.from({ length: 3 }).map((_, i) => (
                        <TableRow key={i}>
                          {Array.from({ length: 6 }).map((__, j) => (
                            <TableCell key={j} className={j === 0 ? "pl-6" : ""}>
                              <Skeleton className="h-5 w-20" />
                            </TableCell>
                          ))}
                        </TableRow>
                      ))
                    ) : purchases.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6}>
                          <p className="py-8 text-center text-sm text-muted-foreground">
                            Aucun achat enregistré. Importez des factures contenant ce produit.
                          </p>
                        </TableCell>
                      </TableRow>
                    ) : (
                      purchases.map((p) => (
                        <TableRow key={p.id}>
                          <TableCell className="pl-6 text-muted-foreground">{formatDate(p.purchase_date)}</TableCell>
                          <TableCell>{p.supplier_name ?? "—"}</TableCell>
                          <TableCell className="tabular-nums">{formatNumber(p.qty)} {p.unit_code ?? ""}</TableCell>
                          <TableCell className="tabular-nums">{formatCurrency(p.total_price, p.currency ?? "EUR")}</TableCell>
                          <TableCell className="tabular-nums">{formatCurrency(p.unit_cost_standard, p.currency ?? "EUR")}/{p.unit_code ?? "u"}</TableCell>
                          <TableCell className="pr-6"><Variation pct={p.variation_pct} /></TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ---------- Factures ---------- */}
        <TabsContent value="invoices">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Factures contenant ce produit</CardTitle>
            </CardHeader>
            <CardContent className="px-0">
              {!invoices || invoices.length === 0 ? (
                <p className="px-6 py-8 text-center text-sm text-muted-foreground">Aucune facture pour ce produit.</p>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="pl-6">Date</TableHead>
                        <TableHead>N°</TableHead>
                        <TableHead>Fournisseur</TableHead>
                        <TableHead>Qté produit</TableHead>
                        <TableHead>Total produit</TableHead>
                        <TableHead className="pr-6 text-right">Ouvrir</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invoices.map((inv) => (
                        <TableRow key={inv.invoice_id}>
                          <TableCell className="pl-6 text-muted-foreground">{formatDate(inv.date)}</TableCell>
                          <TableCell>{inv.invoice_number ?? "—"}</TableCell>
                          <TableCell>{inv.supplier_name ?? "—"}</TableCell>
                          <TableCell className="tabular-nums">{formatNumber(inv.qty)}</TableCell>
                          <TableCell className="tabular-nums">{formatCurrency(inv.line_total, inv.currency ?? "EUR")}</TableCell>
                          <TableCell className="pr-6 text-right">
                            <Button asChild variant="ghost" size="sm">
                              <Link href={`/factures/${inv.invoice_id}`}>
                                <ExternalLink className="h-4 w-4" />
                              </Link>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ---------- Recettes ---------- */}
        <TabsContent value="recipes">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recettes utilisant ce produit</CardTitle>
            </CardHeader>
            <CardContent>
              {!recipes || recipes.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">Aucune recette n&apos;utilise ce produit.</p>
              ) : (
                <ul className="divide-y">
                  {recipes.map((r) => (
                    <li key={r.recipe_id} className="flex items-center justify-between py-3">
                      <div>
                        <p className="font-medium">{r.name}</p>
                        {r.qty != null && (
                          <p className="text-xs text-muted-foreground">{formatNumber(r.qty)} {r.unit ?? ""}</p>
                        )}
                      </div>
                      <Button asChild variant="ghost" size="sm">
                        <Link href={`/recettes/${r.recipe_id}`}>
                          <ExternalLink className="h-4 w-4" />
                          <span className="ml-1">Ouvrir</span>
                        </Link>
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ---------- Statistiques ---------- */}
        <TabsContent value="stats">
          {!stats ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                Pas encore de données d&apos;achat pour ce produit.
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Stat label="Achats enregistrés" value={String(stats.count)} />
              <Stat label="Fournisseurs" value={String(suppliers.length)} />
              <Stat label="Recettes utilisatrices" value={String(recipes?.length ?? 0)} />
              <Stat label="Prix moyen" value={formatCurrency(stats.avg, stats.currency)} />
              <Stat label="Prix minimum" value={formatCurrency(stats.min, stats.currency)} />
              <Stat label="Prix maximum" value={formatCurrency(stats.max, stats.currency)} />
              <Stat label="Dernier prix" value={`${formatCurrency(stats.last, stats.currency)}/${stats.unit}`} />
              <Stat label="Variation globale" value={stats.variation != null ? `${stats.variation > 0 ? "+" : ""}${stats.variation.toFixed(1)} %` : "—"} />
              <Stat label="Factures" value={String(invoices?.length ?? 0)} />
            </div>
          )}
        </TabsContent>
      </Tabs>

      {product && <ProductFormDialog open={editOpen} onOpenChange={setEditOpen} product={product} />}
      <ProductSupplierDialog
        productId={productId}
        open={supplierDialog.open}
        onOpenChange={(o) => setSupplierDialog((prev) => ({ ...prev, open: o }))}
        existing={supplierDialog.row}
        linkedSupplierIds={linkedIds}
      />
      <AlertDialog open={Boolean(deleteLink)} onOpenChange={(o) => !o && setDeleteLink(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Retirer ce fournisseur ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {deleteLink?.supplier_name} » sera retiré du catalogue de ce produit. Les prix déjà relevés sont conservés.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteLink?.link_id) deleteSupplier.mutate(deleteLink.link_id);
                setDeleteLink(null);
              }}
            >
              Retirer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-medium">{value ?? "—"}</p>
    </div>
  );
}
