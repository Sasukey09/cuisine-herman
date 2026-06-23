"use client";

import { useState, type FormEvent } from "react";
import { Loader2, Plus, Trash2, Calculator, FlaskConical } from "lucide-react";
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
import { formatCurrency, formatPercent } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  useMetrics,
  useMetricVariables,
  useCreateMetric,
  useDeleteMetric,
  useEvaluateRecipeMetrics,
} from "@/hooks/use-metrics";
import { useRecipes } from "@/hooks/use-recipes";

const FORMATS = [
  { value: "number", label: "Nombre" },
  { value: "currency", label: "Montant (€)" },
  { value: "percent", label: "Pourcentage" },
];

function formatValue(value: number | null, format: string): string {
  if (value == null) return "—";
  if (format === "currency") return formatCurrency(value);
  if (format === "percent") return formatPercent(value);
  return value.toLocaleString("fr-FR");
}

const selectClass =
  "h-10 rounded-md border border-input bg-card px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function MetricsView() {
  const metrics = useMetrics();
  const variables = useMetricVariables();
  const recipes = useRecipes();
  const create = useCreateMetric();
  const remove = useDeleteMetric();

  const [name, setName] = useState("");
  const [formula, setFormula] = useState("");
  const [format, setFormat] = useState("number");
  const [recipeId, setRecipeId] = useState("");
  const [sellingPrice, setSellingPrice] = useState("");

  const evaluation = useEvaluateRecipeMetrics(
    recipeId || undefined,
    sellingPrice ? Number(sellingPrice) : undefined,
  );

  function insertVar(v: string) {
    setFormula((f) => (f ? `${f} ${v}` : v));
  }

  function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !formula.trim()) {
      toast.error("Nom et formule requis.");
      return;
    }
    create.mutate(
      { name: name.trim(), formula: formula.trim(), format },
      {
        onSuccess: () => {
          toast.success("Indicateur créé.");
          setName("");
          setFormula("");
          setFormat("number");
        },
        onError: (err) => toast.error(getApiErrorMessage(err)),
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Indicateurs personnalisés"
        description="Créez vos propres calculs avec des formules, sans développeur. Ils s'appliquent aux recettes."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Create */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Calculator className="h-5 w-5" />
              Nouvel indicateur
            </CardTitle>
            <CardDescription>
              Ex. « Prix de vente conseillé » = <code>cost_per_portion * 3</code>
            </CardDescription>
          </CardHeader>
          <form onSubmit={onCreate}>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="m-name">Nom</Label>
                  <Input id="m-name" value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="m-format">Format</Label>
                  <select
                    id="m-format"
                    value={format}
                    onChange={(e) => setFormat(e.target.value)}
                    className={cn(selectClass, "w-full")}
                  >
                    {FORMATS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="m-formula">Formule</Label>
                <Input
                  id="m-formula"
                  value={formula}
                  onChange={(e) => setFormula(e.target.value)}
                  placeholder="cost_per_portion * 3"
                  className="font-mono"
                />
                <p className="text-xs text-muted-foreground">
                  Opérateurs : + - * / ( ) · fonctions : min, max, round, abs · ternaire :{" "}
                  <code>a if cond else b</code>
                </p>
                <div className="flex flex-wrap gap-1 pt-1">
                  {(variables.data ?? []).map((v) => (
                    <button
                      key={v.name}
                      type="button"
                      title={v.description}
                      onClick={() => insertVar(v.name)}
                      className="rounded-full border px-2 py-0.5 font-mono text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                    >
                      {v.name}
                    </button>
                  ))}
                </div>
              </div>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                <span className="ml-1">Créer</span>
              </Button>
            </CardContent>
          </form>
        </Card>

        {/* Evaluate */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FlaskConical className="h-5 w-5" />
              Tester sur une recette
            </CardTitle>
            <CardDescription>Voir la valeur de vos indicateurs pour une recette.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="m-recipe">Recette</Label>
                <select
                  id="m-recipe"
                  value={recipeId}
                  onChange={(e) => setRecipeId(e.target.value)}
                  className={cn(selectClass, "w-full")}
                >
                  <option value="">— choisir —</option>
                  {(recipes.data ?? []).map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="m-sp">Prix de vente / portion (optionnel)</Label>
                <Input
                  id="m-sp"
                  type="number"
                  value={sellingPrice}
                  onChange={(e) => setSellingPrice(e.target.value)}
                  placeholder="ex. 12"
                />
              </div>
            </div>

            {recipeId && evaluation.isLoading && (
              <p className="text-sm text-muted-foreground">Calcul…</p>
            )}
            {evaluation.data && (
              <div className="space-y-2">
                {evaluation.data.metrics.length === 0 && (
                  <p className="text-sm text-muted-foreground">Aucun indicateur défini.</p>
                )}
                {evaluation.data.metrics.map((m) => (
                  <div key={m.id} className="flex items-center justify-between border-b py-1.5 text-sm">
                    <span>{m.name}</span>
                    {m.error ? (
                      <span className="text-destructive">{m.error}</span>
                    ) : (
                      <strong>{formatValue(m.value, m.format)}</strong>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* List */}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Mes indicateurs</CardTitle>
        </CardHeader>
        <CardContent>
          {metrics.isLoading && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {metrics.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun indicateur pour l&apos;instant.</p>
          )}
          <div className="space-y-2">
            {(metrics.data ?? []).map((m) => (
              <div key={m.id} className="flex items-center justify-between gap-3 border-b py-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{m.name}</span>
                    <Badge variant="secondary">{m.format}</Badge>
                  </div>
                  <code className="text-xs text-muted-foreground">{m.formula}</code>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() =>
                    remove.mutate(m.id, {
                      onSuccess: () => toast.success("Indicateur supprimé."),
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
