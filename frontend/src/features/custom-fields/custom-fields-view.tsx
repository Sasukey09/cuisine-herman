"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Plus, Trash2, SlidersHorizontal, Save } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
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
import { cn } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  useCustomFields,
  useCreateField,
  useDeleteField,
  useEntityValues,
  useSetEntityValues,
} from "@/hooks/use-custom-fields";
import { useProducts } from "@/hooks/use-products";
import { useRecipes } from "@/hooks/use-recipes";

const TARGETS = [
  { value: "product", label: "Produit" },
  { value: "recipe", label: "Recette" },
];
const TYPES = [
  { value: "text", label: "Texte" },
  { value: "number", label: "Nombre" },
  { value: "boolean", label: "Oui/Non" },
  { value: "select", label: "Liste de choix" },
];

const selectClass =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function CustomFieldsView() {
  // --- definitions ---
  const allDefs = useCustomFields();
  const create = useCreateField();
  const remove = useDeleteField();

  const [label, setLabel] = useState("");
  const [defTarget, setDefTarget] = useState("product");
  const [type, setType] = useState("text");
  const [options, setOptions] = useState("");
  const [required, setRequired] = useState(false);

  function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!label.trim()) {
      toast.error("Libellé requis.");
      return;
    }
    create.mutate(
      {
        label: label.trim(),
        target: defTarget,
        type,
        required,
        options:
          type === "select"
            ? options.split(",").map((o) => o.trim()).filter(Boolean)
            : [],
      },
      {
        onSuccess: () => {
          toast.success("Champ créé.");
          setLabel("");
          setOptions("");
          setRequired(false);
          setType("text");
        },
        onError: (err) => toast.error(getApiErrorMessage(err)),
      },
    );
  }

  // --- value editor ---
  const [valTarget, setValTarget] = useState("product");
  const [entityId, setEntityId] = useState("");
  const products = useProducts();
  const recipes = useRecipes();
  const valuesQuery = useEntityValues(valTarget, entityId || undefined);
  const setValues = useSetEntityValues();
  const [draft, setDraft] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (valuesQuery.data) setDraft(valuesQuery.data.values ?? {});
  }, [valuesQuery.data]);

  const entities = valTarget === "product" ? products.data ?? [] : recipes.data ?? [];

  function onSaveValues() {
    setValues.mutate(
      { target: valTarget, entityId, values: draft },
      {
        onSuccess: () => toast.success("Valeurs enregistrées."),
        onError: (err) => toast.error(getApiErrorMessage(err)),
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Champs personnalisés"
        description="Ajoutez vos propres champs aux produits et recettes, sans développeur."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Definitions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <SlidersHorizontal className="h-5 w-5" />
              Nouveau champ
            </CardTitle>
            <CardDescription>Ex. « Origine » (liste), « DLC (jours) » (nombre).</CardDescription>
          </CardHeader>
          <form onSubmit={onCreate}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="f-label">Libellé</Label>
                <Input id="f-label" value={label} onChange={(e) => setLabel(e.target.value)} />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="f-target">S&apos;applique à</Label>
                  <select id="f-target" value={defTarget} onChange={(e) => setDefTarget(e.target.value)} className={selectClass}>
                    {TARGETS.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="f-type">Type</Label>
                  <select id="f-type" value={type} onChange={(e) => setType(e.target.value)} className={selectClass}>
                    {TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              {type === "select" && (
                <div className="space-y-2">
                  <Label htmlFor="f-options">Choix (séparés par des virgules)</Label>
                  <Input id="f-options" value={options} onChange={(e) => setOptions(e.target.value)} placeholder="France, Italie, Espagne" />
                </div>
              )}
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
                Champ obligatoire
              </label>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                <span className="ml-1">Créer</span>
              </Button>
            </CardContent>
          </form>
        </Card>

        {/* Value editor */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Renseigner sur une fiche</CardTitle>
            <CardDescription>Saisir les valeurs des champs pour un produit ou une recette.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Type de fiche</Label>
                <select
                  value={valTarget}
                  onChange={(e) => {
                    setValTarget(e.target.value);
                    setEntityId("");
                  }}
                  className={selectClass}
                >
                  {TARGETS.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Fiche</Label>
                <select value={entityId} onChange={(e) => setEntityId(e.target.value)} className={selectClass}>
                  <option value="">— choisir —</option>
                  {entities.map((e) => (
                    <option key={e.id} value={e.id}>{e.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {entityId && valuesQuery.data && (
              <div className="space-y-3">
                {valuesQuery.data.definitions.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Aucun champ défini pour ce type. Créez-en un à gauche.
                  </p>
                )}
                {valuesQuery.data.definitions.map((d) => {
                  const key = d.key as string;
                  const value = draft[key];
                  return (
                    <div key={d.id} className="space-y-1.5">
                      <Label>
                        {d.label}
                        {d.required && <span className="text-destructive"> *</span>}
                      </Label>
                      {d.type === "boolean" ? (
                        <input
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(e) => setDraft((p) => ({ ...p, [key]: e.target.checked }))}
                        />
                      ) : d.type === "select" ? (
                        <select
                          value={(value as string) ?? ""}
                          onChange={(e) => setDraft((p) => ({ ...p, [key]: e.target.value }))}
                          className={selectClass}
                        >
                          <option value="">—</option>
                          {d.options.map((o) => (
                            <option key={o} value={o}>{o}</option>
                          ))}
                        </select>
                      ) : (
                        <Input
                          type={d.type === "number" ? "number" : "text"}
                          value={(value as string | number) ?? ""}
                          onChange={(e) => setDraft((p) => ({ ...p, [key]: e.target.value }))}
                        />
                      )}
                    </div>
                  );
                })}
                {valuesQuery.data.definitions.length > 0 && (
                  <Button onClick={onSaveValues} disabled={setValues.isPending}>
                    {setValues.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    <span className="ml-1">Enregistrer</span>
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* List of definitions */}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Champs définis</CardTitle>
        </CardHeader>
        <CardContent>
          {allDefs.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun champ pour l&apos;instant.</p>
          )}
          <div className="space-y-2">
            {(allDefs.data ?? []).map((d) => (
              <div key={d.id} className="flex items-center justify-between gap-3 border-b py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{d.label}</span>
                  <Badge variant="secondary">{d.target === "product" ? "Produit" : "Recette"}</Badge>
                  <Badge variant="outline">{d.type}</Badge>
                  {d.required && <Badge>obligatoire</Badge>}
                  {d.type === "select" && d.options.length > 0 && (
                    <span className="text-xs text-muted-foreground">({d.options.join(", ")})</span>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() =>
                    remove.mutate(d.id, {
                      onSuccess: () => toast.success("Champ supprimé."),
                      onError: (err) => toast.error(getApiErrorMessage(err)),
                    })
                  }
                  aria-label="Supprimer"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </>
  );
}
