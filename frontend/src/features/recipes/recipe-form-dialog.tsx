"use client";

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
import { useCreateRecipe } from "@/hooks/use-recipes";

const numberOptional = z.preprocess(
  (v) => (v === "" || v == null ? undefined : Number(v)),
  z.number().positive("Doit être positif").optional(),
);

const schema = z.object({
  name: z.string().min(1, "Nom requis"),
  yield_qty: numberOptional,
});

type Values = z.infer<typeof schema>;

export function RecipeFormDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const create = useCreateRecipe();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = (values: Values) => {
    create.mutate(
      { name: values.name, yield_qty: values.yield_qty ?? null },
      {
        onSuccess: () => {
          reset({ name: "", yield_qty: undefined });
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle recette</DialogTitle>
          <DialogDescription>
            Créez la recette, puis ajoutez sa fiche technique (ingrédients).
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
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Créer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
