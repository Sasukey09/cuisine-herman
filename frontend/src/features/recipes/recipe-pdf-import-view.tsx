"use client";

import { useState, useRef, type ChangeEvent } from "react";
import Link from "next/link";
import {
  Loader2,
  Wand2,
  Plus,
  Trash2,
  CheckCircle2,
  FileText,
  AlertTriangle,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

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
import { getApiErrorMessage } from "@/lib/api-error";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { useImportRecipePdf, useSaveRecipeImport } from "@/hooks/use-recipes";
import { useProducts } from "@/hooks/use-products";
import type { RecipeImportSaveResult } from "@/services/types";

interface Row {
  name: string;
  quantity: number | null;
  unit: string | null;
  product_id: string | null;
  matched_product_name: string | null;
  match_confidence: number | null;
}

const SELECT_CLASS =
  "h-9 w-44 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

export function RecipePdfImportView() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [portions, setPortions] = useState<string>("");
  const [rows, setRows] = useState<Row[]>([]);
  const [steps, setSteps] = useState<string>("");
  const [hasDraft, setHasDraft] = useState(false);
  const [saved, setSaved] = useState<RecipeImportSaveResult | null>(null);
  const [jobId, setJobId] = useState<string | undefined>(undefined);

  const { data: products } = useProducts();
  const importPdf = useImportRecipePdf();
  const save = useSaveRecipeImport();

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSaved(null);
    importPdf.mutate(file, {
      onSuccess: (status) => {
        if (status.status === "error" || !status.preview) {
          toast.error(status.error || "Aucune recette détectée dans ce PDF.");
          setHasDraft(false);
          return;
        }
        const p = status.preview;
        setJobId(status.job_id);
        setName(p.recipe_name);
        setPortions(p.servings ? String(p.servings) : "");
        setRows(
          p.ingredients.map((i) => ({
            name: i.name,
            quantity: i.quantity,
            unit: i.unit,
            product_id: i.matched_product_id,
            matched_product_name: i.matched_product_name,
            match_confidence: i.match_confidence,
          })),
        );
        setSteps((p.instructions ?? []).join("\n"));
        setHasDraft(true);
        toast.success("Recette extraite — vérifiez avant d'enregistrer.");
      },
      onError: (err) => toast.error(getApiErrorMessage(err)),
    });
    e.target.value = ""; // allow re-selecting the same file
  }

  function updateRow(i: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((prev) => [
      ...prev,
      { name: "", quantity: null, unit: "", product_id: null, matched_product_name: null, match_confidence: null },
    ]);
  }
  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, idx) => idx !== i));
  }

  function onSave() {
    if (!name.trim()) {
      toast.error("Donnez un nom à la recette.");
      return;
    }
    const ingredients = rows
      .filter((r) => r.name.trim())
      .map((r) => ({
        name: r.name.trim(),
        quantity: r.quantity === null || (r.quantity as unknown) === "" ? null : Number(r.quantity),
        unit: r.unit?.trim() || null,
        product_id: r.product_id || null,
      }));
    if (ingredients.length === 0) {
      toast.error("Ajoutez au moins un ingrédient.");
      return;
    }
    const instructions = steps
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    save.mutate(
      {
        payload: {
          recipe_name: name.trim(),
          servings: portions ? Number(portions) : null,
          instructions,
          ingredients,
        },
        jobId,
      },
      {
        onSuccess: (res) => {
          setSaved(res);
          setHasDraft(false);
        },
      },
    );
  }

  return (
    <>
      <BackButton />
      <PageHeader
        title="Importer une recette PDF"
        description="Déposez un PDF de recette (texte, scanné ou image). L'IA en extrait une fiche technique modifiable, associe les produits de votre catalogue et la chiffre."
      />

      <input
        ref={fileRef}
        type="file"
        accept="application/pdf,image/*"
        className="hidden"
        onChange={onFile}
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => fileRef.current?.click()} disabled={importPdf.isPending}>
          {importPdf.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Upload className="h-4 w-4" />
          )}
          <span className="ml-2">Choisir un PDF</span>
        </Button>
        <span className="text-xs text-muted-foreground">
          PDF texte, PDF scanné ou image — l&apos;OCR s&apos;en charge.
        </span>
      </div>

      {hasDraft && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Wand2 className="h-4 w-4" />
              Fiche extraite (modifiable)
            </CardTitle>
            <CardDescription className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" />
              Vérifiez les quantités, les unités et les correspondances produits avant d&apos;enregistrer.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="ri-name">Nom de la recette</Label>
                <Input id="ri-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ri-portions">Portions</Label>
                <Input
                  id="ri-portions"
                  type="number"
                  min={1}
                  value={portions}
                  onChange={(e) => setPortions(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Ingrédients</Label>
              <div className="space-y-2">
                {rows.map((r, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <Input
                      value={r.name}
                      onChange={(e) => updateRow(i, { name: e.target.value })}
                      placeholder="Ingrédient"
                      className="min-w-40 flex-1"
                    />
                    <Input
                      type="number"
                      value={r.quantity ?? ""}
                      onChange={(e) =>
                        updateRow(i, { quantity: e.target.value === "" ? null : Number(e.target.value) })
                      }
                      placeholder="Qté"
                      className="w-20"
                    />
                    <Input
                      value={r.unit ?? ""}
                      onChange={(e) => updateRow(i, { unit: e.target.value })}
                      placeholder="unité"
                      className="w-20"
                    />
                    <select
                      className={SELECT_CLASS}
                      value={r.product_id ?? ""}
                      onChange={(e) => updateRow(i, { product_id: e.target.value || null })}
                      aria-label="Produit associé"
                    >
                      <option value="">— à créer / non associé —</option>
                      {products?.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeRow(i)}
                      aria-label="Supprimer"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button type="button" variant="outline" size="sm" onClick={addRow}>
                <Plus className="h-4 w-4" />
                <span className="ml-1">Ajouter un ingrédient</span>
              </Button>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ri-steps">Étapes (une par ligne)</Label>
              <textarea
                id="ri-steps"
                value={steps}
                onChange={(e) => setSteps(e.target.value)}
                rows={6}
                className="w-full rounded-md border border-input bg-background p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button onClick={onSave} disabled={save.isPending}>
                {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                <span className={save.isPending ? "ml-2" : ""}>Enregistrer la fiche</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {saved && (
        <Card className="mt-4 border-emerald-500/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              Fiche enregistrée
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex flex-wrap gap-4">
              <span>
                Coût matière : <strong>{formatCurrency(saved.cost.computed_cost_total ?? 0)}</strong>
              </span>
              <span>
                Coût / portion : <strong>{formatCurrency(saved.cost.cost_per_portion ?? 0)}</strong>
              </span>
              {saved.cost.food_cost_pct != null && (
                <span>
                  Food cost : <strong>{formatPercent(saved.cost.food_cost_pct)}</strong>
                </span>
              )}
              {saved.cost.margin_estimated != null && (
                <span>
                  Marge : <strong>{formatCurrency(saved.cost.margin_estimated)}</strong>
                </span>
              )}
            </div>
            {saved.cost.has_missing_prices && (
              <p className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                <AlertTriangle className="h-4 w-4" />
                Certains ingrédients n&apos;ont pas de prix — le coût est incomplet.
              </p>
            )}
            {saved.unmatched_ingredients.length > 0 && (
              <p className="text-muted-foreground">
                Produits à créer : {saved.unmatched_ingredients.join(", ")}
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <Button asChild variant="outline" size="sm">
                <Link href={`/recettes/${saved.recipe_id}`}>
                  <FileText className="h-4 w-4" />
                  <span className="ml-1">Ouvrir la fiche</span>
                </Link>
              </Button>
              <Badge variant="secondary">{saved.name}</Badge>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
