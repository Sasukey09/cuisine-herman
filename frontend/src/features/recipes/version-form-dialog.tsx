"use client";

import { useEffect } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Plus, Trash2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useProducts } from "@/hooks/use-products";
import { useCreateVersion } from "@/hooks/use-recipes";

const num = (s: z.ZodTypeAny) =>
  z.preprocess((v) => (v === "" || v == null ? undefined : Number(v)), s);

const ingredientSchema = z.object({
  product_id: z.string().min(1, "Produit requis"),
  qty: num(z.number().positive("Qté > 0")),
  loss_pct: num(z.number().min(0).max(100).optional()),
  yield_pct: num(z.number().min(1).max(100).optional()),
});

const schema = z.object({
  ingredients: z.array(ingredientSchema).min(1, "Ajoutez au moins un ingrédient"),
});

type Values = z.infer<typeof schema>;

const emptyRow = { product_id: "", qty: undefined, loss_pct: 0, yield_pct: 100 };

export interface InitialIngredient {
  product_id: string;
  qty?: number;
  loss_pct?: number;
  yield_pct?: number;
}

export function VersionFormDialog({
  open,
  onOpenChange,
  recipeId,
  initialIngredients,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recipeId: string;
  // Pre-fill with the recipe's current ingredients so the user builds on them —
  // adds a 2nd/3rd, edits or removes one — instead of re-entering everything.
  // Saving writes a new version with the full list (which becomes current).
  initialIngredients?: InitialIngredient[];
}) {
  const { data: products } = useProducts();
  const create = useCreateVersion(recipeId);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { ingredients: [{ ...emptyRow }] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "ingredients" });

  useEffect(() => {
    if (!open) return;
    const rows =
      initialIngredients && initialIngredients.length > 0
        ? initialIngredients.map((i) => ({
            product_id: i.product_id ?? "",
            qty: i.qty,
            loss_pct: i.loss_pct ?? 0,
            yield_pct: i.yield_pct ?? 100,
          }))
        : [{ ...emptyRow }];
    reset({ ingredients: rows });
    // Depend on the serialized ingredients so reopening after a save reflects
    // the latest saved list (incremental building).
  }, [open, reset, JSON.stringify(initialIngredients)]); // eslint-disable-line react-hooks/exhaustive-deps

  const onSubmit = (values: Values) => {
    const payload = {
      ingredients: values.ingredients.map((i) => ({
        product_id: i.product_id,
        qty: i.qty,
        // No unit picker yet: treat qty as already expressed in the base unit.
        qty_normalized: i.qty,
        loss_pct: i.loss_pct ?? 0,
        yield_pct: i.yield_pct ?? 100,
      })),
    };
    create.mutate(payload, { onSuccess: () => onOpenChange(false) });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Fiche technique</DialogTitle>
          <DialogDescription>
            Ajoutez les ingrédients (quantité dans l&apos;unité de base, perte et rendement
            en %).
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-3">
            <div className="hidden grid-cols-[1fr_80px_70px_70px_36px] gap-2 px-1 text-xs text-muted-foreground sm:grid">
              <span>Produit</span>
              <span>Qté</span>
              <span>Perte %</span>
              <span>Rdt %</span>
              <span />
            </div>
            {fields.map((field, index) => (
              <div
                key={field.id}
                className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_80px_70px_70px_36px]"
              >
                <select
                  className="col-span-2 h-10 rounded-md border border-input bg-background px-3 text-sm sm:col-span-1"
                  {...register(`ingredients.${index}.product_id`)}
                >
                  <option value="">Choisir…</option>
                  {products?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <Input type="number" step="any" placeholder="Qté" {...register(`ingredients.${index}.qty`)} />
                <Input type="number" step="any" placeholder="0" {...register(`ingredients.${index}.loss_pct`)} />
                <Input type="number" step="any" placeholder="100" {...register(`ingredients.${index}.yield_pct`)} />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Retirer"
                  onClick={() => remove(index)}
                  disabled={fields.length === 1}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {errors.ingredients?.message && (
              <p className="text-sm text-destructive">{errors.ingredients.message}</p>
            )}
            {Array.isArray(errors.ingredients) &&
              errors.ingredients.some((e) => e) && (
                <p className="text-sm text-destructive">
                  Vérifiez les lignes : produit et quantité sont requis.
                </p>
              )}
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => append({ ...emptyRow })}
          >
            <Plus className="h-4 w-4" />
            Ajouter un ingrédient
          </Button>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
