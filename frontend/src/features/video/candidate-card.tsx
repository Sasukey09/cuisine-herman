"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  ListChecks,
  Merge,
  Plus,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { VideoIngredientDraft, VideoRecipeCandidate } from "@/services/types";

export interface CandidateState extends VideoRecipeCandidate {
  selected: boolean;
}

export function emojiFor(name: string): string {
  const n = (name || "").toLowerCase();
  if (/(gâteau|gateau|tarte|dessert|cake|cookie)/.test(n)) return "🍰";
  if (/(salade|crudité)/.test(n)) return "🥗";
  if (/(soupe|velouté|potage)/.test(n)) return "🍲";
  if (/(pâtes|pates|pasta|spaghetti|lasagne)/.test(n)) return "🍝";
  return "🍽️";
}

/** mm:ss for a duration in seconds. */
function fmtTime(sec: number): string {
  const total = Math.max(0, Math.floor(sec));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function timeLabel(prep: number | null, cook: number | null): string | null {
  if (prep == null && cook == null) return null;
  const parts: string[] = [];
  if (prep != null) parts.push(`${prep} min prépa`);
  if (cook != null) parts.push(`${cook} min cuisson`);
  return parts.join(" · ");
}

/** Turn a textarea's raw text into a string[], one entry per line (kept as-typed). */
function textToLines(text: string): string[] {
  return text.split("\n");
}

export function CandidateCard({
  value,
  index,
  videoId,
  onChange,
  onDelete,
  onToggle,
  onMerge,
  mergeSource = false,
}: {
  value: CandidateState;
  index: number;
  videoId: string | null;
  onChange: (v: CandidateState) => void;
  onDelete: () => void;
  onToggle: () => void;
  onMerge: () => void;
  mergeSource?: boolean;
}) {
  const [open, setOpen] = useState(false);

  function set<K extends keyof CandidateState>(key: K, v: CandidateState[K]) {
    onChange({ ...value, [key]: v });
  }

  function updateIngredient(i: number, patch: Partial<VideoIngredientDraft>) {
    set(
      "ingredients",
      value.ingredients.map((r, idx) => (idx === i ? { ...r, ...patch } : r)),
    );
  }
  function addIngredient() {
    set("ingredients", [...value.ingredients, { name: "", qty: null, unit: "" }]);
  }
  function removeIngredient(i: number) {
    set(
      "ingredients",
      value.ingredients.filter((_, idx) => idx !== i),
    );
  }

  const deepLink =
    videoId && value.start_sec != null
      ? `https://youtu.be/${videoId}?t=${Math.floor(value.start_sec)}`
      : null;
  const timeChip =
    value.start_sec != null
      ? `${fmtTime(value.start_sec)}${value.end_sec != null ? `–${fmtTime(value.end_sec)}` : ""}`
      : null;
  const time = timeLabel(value.prep_time_min, value.cook_time_min);
  const ingredientCount = value.ingredients.length;

  return (
    <Card className={cn("mt-3", mergeSource && "ring-2 ring-primary")}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0 pb-3">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={value.selected}
            onChange={onToggle}
            className="mt-1 h-4 w-4 shrink-0 rounded border-input accent-primary"
            aria-label={`Sélectionner ${value.name || `recette ${index + 1}`}`}
          />
          <span className="text-2xl leading-none" aria-hidden>
            {emojiFor(value.name)}
          </span>
          <div>
            <CardTitle className="text-base">{value.name || `Recette ${index + 1}`}</CardTitle>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {value.yield_qty != null && (
                <Badge variant="secondary">{value.yield_qty} portions</Badge>
              )}
              {time && (
                <Badge variant="secondary">
                  <Clock className="mr-1 h-3 w-3" />
                  {time}
                </Badge>
              )}
              <Badge variant="secondary">
                <ListChecks className="mr-1 h-3 w-3" />
                {ingredientCount} ingrédient{ingredientCount === 1 ? "" : "s"}
              </Badge>
              {timeChip &&
                (deepLink ? (
                  <a
                    href={deepLink}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors hover:bg-accent hover:text-accent-foreground"
                  >
                    {timeChip}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <Badge variant="outline">{timeChip}</Badge>
                ))}
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            variant={mergeSource ? "secondary" : "ghost"}
            size="icon"
            onClick={onMerge}
            aria-label="Fusionner"
            title="Fusionner avec une autre carte"
          >
            <Merge className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onDelete}
            aria-label="Supprimer"
            title="Supprimer cette recette"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            <span className="ml-1">{open ? "Réduire" : "Éditer"}</span>
          </Button>
        </div>
      </CardHeader>

      {open && (
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor={`c-name-${index}`}>Nom</Label>
              <Input
                id={`c-name-${index}`}
                value={value.name}
                onChange={(e) => set("name", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`c-portions-${index}`}>Portions</Label>
              <Input
                id={`c-portions-${index}`}
                type="number"
                min={1}
                value={value.yield_qty ?? ""}
                onChange={(e) =>
                  set("yield_qty", e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor={`c-prep-${index}`}>Temps de préparation (min)</Label>
              <Input
                id={`c-prep-${index}`}
                type="number"
                min={0}
                value={value.prep_time_min ?? ""}
                onChange={(e) =>
                  set("prep_time_min", e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`c-cook-${index}`}>Temps de cuisson (min)</Label>
              <Input
                id={`c-cook-${index}`}
                type="number"
                min={0}
                value={value.cook_time_min ?? ""}
                onChange={(e) =>
                  set("cook_time_min", e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor={`c-summary-${index}`}>Résumé</Label>
            <Input
              id={`c-summary-${index}`}
              value={value.summary ?? ""}
              onChange={(e) => set("summary", e.target.value || null)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor={`c-description-${index}`}>Description</Label>
            <textarea
              id={`c-description-${index}`}
              value={value.description ?? ""}
              onChange={(e) => set("description", e.target.value || null)}
              rows={2}
              className="w-full rounded-md border border-input bg-background p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          <div className="space-y-2">
            <Label>Ingrédients</Label>
            <div className="space-y-2">
              {value.ingredients.map((r, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input
                    value={r.name}
                    onChange={(e) => updateIngredient(i, { name: e.target.value })}
                    placeholder="Ingrédient"
                    className="flex-1"
                  />
                  <Input
                    type="number"
                    value={r.qty ?? ""}
                    onChange={(e) =>
                      updateIngredient(i, {
                        qty: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                    placeholder="Qté"
                    className="w-24"
                  />
                  <Input
                    value={r.unit ?? ""}
                    onChange={(e) => updateIngredient(i, { unit: e.target.value })}
                    placeholder="unité"
                    className="w-24"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeIngredient(i)}
                    aria-label="Supprimer l'ingrédient"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <Button type="button" variant="outline" size="sm" onClick={addIngredient}>
              <Plus className="h-4 w-4" />
              <span className="ml-1">Ajouter un ingrédient</span>
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor={`c-steps-${index}`}>Étapes (une par ligne)</Label>
            <textarea
              id={`c-steps-${index}`}
              value={value.steps.join("\n")}
              onChange={(e) => set("steps", textToLines(e.target.value))}
              rows={6}
              className="w-full rounded-md border border-input bg-background p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor={`c-tips-${index}`}>Astuces (une par ligne)</Label>
              <textarea
                id={`c-tips-${index}`}
                value={value.tips.join("\n")}
                onChange={(e) => set("tips", textToLines(e.target.value))}
                rows={3}
                className="w-full rounded-md border border-input bg-background p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`c-variants-${index}`}>Variantes (une par ligne)</Label>
              <textarea
                id={`c-variants-${index}`}
                value={value.variants.join("\n")}
                onChange={(e) => set("variants", textToLines(e.target.value))}
                rows={3}
                className="w-full rounded-md border border-input bg-background p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`c-allergens-${index}`}>Allergènes (un par ligne)</Label>
              <textarea
                id={`c-allergens-${index}`}
                value={value.allergens.join("\n")}
                onChange={(e) => set("allergens", textToLines(e.target.value))}
                rows={3}
                className="w-full rounded-md border border-input bg-background p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
