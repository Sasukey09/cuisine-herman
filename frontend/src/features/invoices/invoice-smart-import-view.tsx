"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Upload, Wand2, AlertTriangle, CheckCircle2 } from "lucide-react";

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
import { useInvoicePreview, useConfirmInvoice } from "@/hooks/use-invoices";
import { useProductCategories, useProducts } from "@/hooks/use-products";
import type { InvoicePreviewLineData, InvoiceConfirmLineData } from "@/services/types";

const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

interface Row extends InvoicePreviewLineData {
  action: "create" | "associate" | "skip";
  category: string;
  product_id: string;
}

export function InvoiceSmartImportView() {
  const router = useRouter();
  const preview = useInvoicePreview();
  const confirm = useConfirmInvoice();
  const { data: categories } = useProductCategories();
  const { data: products } = useProducts();
  const fileRef = useRef<HTMLInputElement>(null);

  const [supplier, setSupplier] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [date, setDate] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
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
        <>
          <input ref={fileRef} type="file" accept=".pdf,image/*" className="hidden" onChange={onFile} />
          <Button onClick={() => fileRef.current?.click()} disabled={preview.isPending}>
            {preview.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            <span className="ml-2">Choisir une facture (PDF / image)</span>
          </Button>
          {preview.isPending && (
            <p className="mt-3 text-sm text-muted-foreground">Analyse OCR en cours…</p>
          )}
        </>
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
                <div key={i} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Input
                      className="min-w-40 flex-1"
                      value={r.description}
                      onChange={(e) => update(i, { description: e.target.value })}
                    />
                    <Input className="w-16" type="number" value={r.qty ?? ""} onChange={(e) => update(i, { qty: e.target.value === "" ? null : Number(e.target.value) })} placeholder="Qté" />
                    <Input className="w-16" value={r.unit ?? ""} onChange={(e) => update(i, { unit: e.target.value })} placeholder="unité" />
                    <Input className="w-20" type="number" value={r.unit_price ?? ""} onChange={(e) => update(i, { unit_price: e.target.value === "" ? null : Number(e.target.value) })} placeholder="PU" />
                    <Input className="w-16" type="number" value={r.vat_rate ?? ""} onChange={(e) => update(i, { vat_rate: e.target.value === "" ? null : Number(e.target.value) })} placeholder="TVA%" />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <select className={`${SELECT_CLASS} w-32`} value={r.action} onChange={(e) => update(i, { action: e.target.value as Row["action"] })}>
                      <option value="create">➕ Créer</option>
                      <option value="associate">🔗 Associer</option>
                      <option value="skip">Ignorer</option>
                    </select>
                    {r.action === "create" && (
                      <select className={`${SELECT_CLASS} w-44`} value={r.category} onChange={(e) => update(i, { category: e.target.value })}>
                        <option value="">Catégorie auto</option>
                        {(categories ?? []).map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    )}
                    {r.action === "associate" && (
                      <select className={`${SELECT_CLASS} w-64`} value={r.product_id} onChange={(e) => update(i, { product_id: e.target.value })}>
                        <option value="">Choisir un produit…</option>
                        {(products ?? []).map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    )}
                    {r.matched_product_name && r.action === "associate" && (
                      <span className="text-xs text-muted-foreground">
                        Suggéré : {r.matched_product_name}
                        {r.match_confidence != null ? ` (${Math.round(r.match_confidence)}%)` : ""}
                      </span>
                    )}
                    {r.needs_review && r.action === "create" && (
                      <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                        <AlertTriangle className="h-3.5 w-3.5" /> nouveau produit
                      </span>
                    )}
                  </div>
                </div>
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
