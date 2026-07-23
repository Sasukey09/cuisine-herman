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
import { useInvoicePreview, useConfirmInvoice } from "@/hooks/use-invoices";
import { useProductCategories, useProducts } from "@/hooks/use-products";
import type { InvoicePreviewLineData, InvoiceConfirmLineData } from "@/services/types";

interface Row extends InvoicePreviewLineData {
  action: ImportAction;
  category: string;
  product_id: string;
}

export function InvoiceSmartImportView() {
  const router = useRouter();
  const preview = useInvoicePreview();
  const confirm = useConfirmInvoice();
  const { data: categories } = useProductCategories();
  const { data: products } = useProducts();

  const [supplier, setSupplier] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [date, setDate] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);

  function onFile(file: File) {
    preview.mutate(file, {
      onSuccess: (res) => {
        setSupplier(res.supplier ?? "");
        setInvoiceNumber(res.invoice_number ?? "");
        setDate(res.date ?? "");
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
    const lines: InvoiceConfirmLineData[] = rows.map((r) => ({
      description: r.description,
      qty: r.qty,
      unit: r.unit,
      unit_price: r.unit_price,
      line_total: r.line_total,
      vat_rate: r.vat_rate,
      action: r.action,
      product_id: r.action === "associate" ? r.product_id || null : null,
      category: r.action === "create" ? r.category || null : null,
    }));
    confirm.mutate(
      { supplier: supplier || null, invoice_number: invoiceNumber || null, date: date || null, currency: "EUR", lines },
      { onSuccess: (res) => router.push(`/factures/${res.invoice_id}`) },
    );
  }

  const toCreate = rows?.filter((r) => r.action === "create").length ?? 0;
  const toAssociate = rows?.filter((r) => r.action === "associate").length ?? 0;

  return (
    <>
      <BackButton fallbackHref="/factures" />
      <PageHeader
        title="Import intelligent de facture"
        description="L'OCR détecte les lignes, suggère les produits (existants ou à créer) et leur catégorie. Vérifiez, puis validez : les produits inexistants sont créés (avec TVA + catégorie) et reliés au fournisseur."
      />

      {!rows ? (
        <ImportFilePicker
          label="Choisir une facture (PDF / image)"
          pending={preview.isPending}
          onFile={onFile}
        />
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Facture détectée</CardTitle>
              <CardDescription>Le fournisseur inexistant sera créé et associé à tous les produits.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="si-supplier">Fournisseur</Label>
                <Input id="si-supplier" value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder="Fournisseur" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="si-number">N° facture</Label>
                <Input id="si-number" value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="si-date">Date</Label>
                <Input id="si-date" type="date" value={date ?? ""} onChange={(e) => setDate(e.target.value)} />
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
                />
              ))}
            </CardContent>
          </Card>

          <div className="flex items-center gap-3">
            <Button onClick={onConfirm} disabled={confirm.isPending}>
              {confirm.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              <span className="ml-2">Valider et importer</span>
            </Button>
            <Button variant="outline" onClick={() => setRows(null)}>Recommencer</Button>
          </div>
        </div>
      )}
    </>
  );
}
