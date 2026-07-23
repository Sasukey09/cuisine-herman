"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Wand2, CheckCircle2 } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { BackButton } from "@/components/back-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ImportFilePicker } from "@/features/imports/import-file-picker";
import { ImportLineRow, type ImportAction } from "@/features/imports/import-line-row";
import { useQuotePreview, useConfirmQuote } from "@/hooks/use-quotes";
import { useProductCategories, useProducts } from "@/hooks/use-products";
import type { QuotePreviewLineData, QuoteConfirmLineData } from "@/services/types";

interface Row extends QuotePreviewLineData {
  action: ImportAction;
  category: string;
  product_id: string;
}

export function QuoteSmartImportView() {
  const router = useRouter();
  const preview = useQuotePreview();
  const confirm = useConfirmQuote();
  const { data: categories } = useProductCategories();
  const { data: products } = useProducts();

  const [supplier, setSupplier] = useState("");
  const [quoteNumber, setQuoteNumber] = useState("");
  const [date, setDate] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [discountTotal, setDiscountTotal] = useState("");
  const [conditions, setConditions] = useState("");
  const [deliveryFee, setDeliveryFee] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);

  function onFile(file: File) {
    preview.mutate(file, {
      onSuccess: (res) => {
        setSupplier(res.supplier ?? "");
        setQuoteNumber(res.quote_number ?? "");
        setDate(res.date ?? "");
        setValidUntil(res.valid_until ?? "");
        setDiscountTotal(res.discount_total != null ? String(res.discount_total) : "");
        setConditions(res.conditions ?? "");
        setDeliveryFee(res.delivery_fee != null ? String(res.delivery_fee) : "");
        setRows(
          res.lines.map((l) => ({
            ...l,
            action: !l.needs_review && l.matched_product_id ? "associate" : "create",
            category: l.suggested_category ?? "",
            product_id: l.matched_product_id ?? "",
          })),
        );
      },
    });
  }

  function update(i: number, patch: Partial<Row>) {
    setRows((prev) => (prev ? prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)) : prev));
  }

  function onConfirm() {
    if (!rows) return;
    const lines: QuoteConfirmLineData[] = rows.map((r) => ({
      description: r.description,
      qty: r.qty,
      unit: r.unit,
      unit_price: r.unit_price,
      line_total: r.line_total,
      vat_rate: r.vat_rate,
      discount_pct: r.discount_pct,
      pack_size: r.pack_size,
      action: r.action,
      product_id: r.action === "associate" ? r.product_id || null : null,
      category: r.action === "create" ? r.category || null : null,
    }));
    confirm.mutate(
      {
        supplier: supplier || null,
        quote_number: quoteNumber || null,
        date: date || null,
        valid_until: validUntil || null,
        discount_total: discountTotal === "" ? null : Number(discountTotal),
        conditions: conditions || null,
        delivery_fee: deliveryFee === "" ? null : Number(deliveryFee),
        currency: "EUR",
        lines,
      },
      { onSuccess: (res) => router.push(`/devis/${res.quote_id}`) },
    );
  }

  const toCreate = rows?.filter((r) => r.action === "create").length ?? 0;
  const toAssociate = rows?.filter((r) => r.action === "associate").length ?? 0;
  const toSkip = rows?.filter((r) => r.action === "skip").length ?? 0;

  return (
    <>
      <BackButton fallbackHref="/devis" />
      <PageHeader
        title="Import de devis"
        description="L'OCR lit le devis du fournisseur, suggère les produits (existants ou à créer) et leur catégorie. Vérifiez, puis validez : les produits inexistants sont créés et rattachés au fournisseur. Les prix restent propres au devis — ils n'entrent pas dans l'historique d'achat."
      />

      {!rows ? (
        <ImportFilePicker
          label="Choisir un devis (PDF / image)"
          pending={preview.isPending}
          onFile={onFile}
        />
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Devis détecté</CardTitle>
              <CardDescription>
                Le fournisseur inexistant sera créé et rattaché aux produits du devis.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="qi-supplier">Fournisseur</Label>
                <Input
                  id="qi-supplier"
                  value={supplier}
                  onChange={(e) => setSupplier(e.target.value)}
                  placeholder="Fournisseur"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="qi-number">N° de devis</Label>
                <Input
                  id="qi-number"
                  value={quoteNumber}
                  onChange={(e) => setQuoteNumber(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="qi-date">Date</Label>
                <Input
                  id="qi-date"
                  type="date"
                  value={date ?? ""}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="qi-valid">Valable jusqu&apos;au</Label>
                <Input
                  id="qi-valid"
                  type="date"
                  value={validUntil ?? ""}
                  onChange={(e) => setValidUntil(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="qi-discount">Remise globale (€)</Label>
                <Input
                  id="qi-discount"
                  type="number"
                  value={discountTotal}
                  onChange={(e) => setDiscountTotal(e.target.value)}
                  placeholder="0"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="qi-delivery">Frais de livraison (€)</Label>
                <Input
                  id="qi-delivery"
                  type="number"
                  value={deliveryFee}
                  onChange={(e) => setDeliveryFee(e.target.value)}
                  placeholder="0"
                />
                <p className="text-[11px] text-muted-foreground">
                  Comptés dans le comparatif : ils changent qui est le moins cher.
                </p>
              </div>
              <div className="space-y-1">
                <Label htmlFor="qi-conditions">Conditions</Label>
                <Input
                  id="qi-conditions"
                  value={conditions}
                  onChange={(e) => setConditions(e.target.value)}
                  placeholder="paiement, livraison…"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <Wand2 className="h-4 w-4" />
                {rows.length} ligne(s) détectée(s)
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{toAssociate} à associer</Badge>
                <Badge variant="warning">{toCreate} à créer</Badge>
                {toSkip > 0 ? <Badge variant="outline">{toSkip} ignorée(s)</Badge> : null}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {rows.map((r, i) => (
                <ImportLineRow
                  key={i}
                  row={r}
                  onChange={(patch) => update(i, patch)}
                  categories={categories}
                  products={products}
                  extraFields={
                    <>
                      <Input
                        className="w-24"
                        type="number"
                        value={r.discount_pct ?? ""}
                        onChange={(e) =>
                          update(i, {
                            discount_pct: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                        placeholder="Rem. %"
                        aria-label="Remise %"
                      />
                      <Input
                        className="w-36"
                        value={r.pack_size ?? ""}
                        onChange={(e) => update(i, { pack_size: e.target.value })}
                        placeholder="Condit."
                        aria-label="Conditionnement"
                      />
                    </>
                  }
                />
              ))}
            </CardContent>
          </Card>

          <div className="flex items-center gap-3">
            <Button onClick={onConfirm} disabled={confirm.isPending}>
              {confirm.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              <span className="ml-2">Valider et importer</span>
            </Button>
            <Button variant="outline" onClick={() => setRows(null)}>
              Recommencer
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
