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
import { useCreateProduct, useUpdateProduct } from "@/hooks/use-products";
import type { Product } from "@/services/types";

const schema = z.object({
  name: z.string().min(1, "Nom requis"),
  sku: z.string().optional(),
});

type Values = z.infer<typeof schema>;

interface ProductFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product?: Product | null;
}

export function ProductFormDialog({ open, onOpenChange, product }: ProductFormDialogProps) {
  const create = useCreateProduct();
  const update = useUpdateProduct();
  const isEdit = Boolean(product);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { name: "", sku: "" } });

  useEffect(() => {
    if (open) reset({ name: product?.name ?? "", sku: product?.sku ?? "" });
  }, [open, product, reset]);

  const pending = create.isPending || update.isPending;

  const onSubmit = (values: Values) => {
    const payload = { name: values.name, sku: values.sku?.trim() || null };
    const opts = { onSuccess: () => onOpenChange(false) };
    if (isEdit && product) update.mutate({ id: product.id, payload }, opts);
    else create.mutate(payload, opts);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Modifier le produit" : "Nouveau produit"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Mettez à jour les informations du produit."
              : "Ajoutez un produit à votre catalogue."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="name">Nom</Label>
            <Input id="name" placeholder="Tomate ronde" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="sku">Référence / SKU (optionnel)</Label>
            <Input id="sku" placeholder="TOM-001" {...register("sku")} />
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
