"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";

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
import { useCreateRecipe, useUpdateRecipe } from "@/hooks/use-recipes";
import type { Recipe } from "@/services/types";

const numberOptional = z.preprocess(
  (v) => (v === "" || v == null ? undefined : Number(v)),
  z.number().positive("Doit être positif").optional(),
);

const schema = z.object({
  name: z.string().min(1, "Nom requis"),
  yield_qty: numberOptional,
  selling_price: numberOptional,
});

type Values = z.infer<typeof schema>;

export function RecipeFormDialog({
  open,
  onOpenChange,
  recipe = null,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null => create, otherwise edit the given recipe */
  recipe?: Recipe | null;
}) {
  const isEdit = recipe !== null;
  const create = useCreateRecipe();
  const update = useUpdateRecipe();
  const pending = create.isPending || update.isPending;
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) {
      reset({
        name: recipe?.name ?? "",
        yield_qty: recipe?.yield_qty ?? undefined,
        selling_price: recipe?.selling_price ?? undefined,
      });
    }
  }, [open, recipe, reset]);

  const onSubmit = (values: Values) => {
    const payload = {
      name: values.name,
      yield_qty: values.yield_qty ?? null,
      selling_price: values.selling_price ?? null,
    };
    const onSuccess = () => onOpenChange(false);
    if (isEdit) {
      update.mutate({ id: recipe!.id, payload }, { onSuccess });
    } else {
      create.mutate(payload, { onSuccess });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Modifier la recette" : "Nouvelle recette"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Modifiez le nom ou le nombre de portions."
              : "Créez la recette, puis ajoutez sa fiche technique (ingrédients)."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="name">Nom</Label>
            <Input id="name" placeholder="Sauce tomate maison" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="yield_qty">Nombre de portions (optionnel)</Label>
            <Input id="yield_qty" type="number" step="any" placeholder="4" {...register("yield_qty")} />
            {errors.yield_qty && (
              <p className="text-sm text-destructive">{errors.yield_qty.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="selling_price">Prix de vente / portion (optionnel)</Label>
            <Input id="selling_price" type="number" step="any" placeholder="12.50" {...register("selling_price")} />
            {errors.selling_price && (
              <p className="text-sm text-destructive">{errors.selling_price.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={pending}>
              {pending && <Loader2 className="h-4 w-4 animate-spin" />}
              {isEdit ? "Enregistrer" : "Créer"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
