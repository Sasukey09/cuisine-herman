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
import { useCreateSupplier, useUpdateSupplier } from "@/hooks/use-suppliers";
import type { Supplier, SupplierPayload } from "@/services/types";

const schema = z.object({
  name: z.string().min(1, "Nom requis"),
  code: z.string().optional(),
  email: z.string().email("Email invalide").or(z.literal("")).optional(),
  phone: z.string().optional(),
});

type Values = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  supplier?: Supplier | null;
}

export function SupplierFormDialog({ open, onOpenChange, supplier }: Props) {
  const create = useCreateSupplier();
  const update = useUpdateSupplier();
  const isEdit = Boolean(supplier);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) {
      reset({
        name: supplier?.name ?? "",
        code: supplier?.code ?? "",
        email: supplier?.contact?.email ?? "",
        phone: supplier?.contact?.phone ?? "",
      });
    }
  }, [open, supplier, reset]);

  const pending = create.isPending || update.isPending;

  const onSubmit = (values: Values) => {
    const contact: Record<string, string> = {};
    if (values.email) contact.email = values.email;
    if (values.phone) contact.phone = values.phone;

    const payload: SupplierPayload = {
      name: values.name,
      code: values.code?.trim() || null,
      contact: Object.keys(contact).length ? contact : null,
    };
    const opts = { onSuccess: () => onOpenChange(false) };
    if (isEdit && supplier) update.mutate({ id: supplier.id, payload }, opts);
    else create.mutate(payload, opts);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Modifier le fournisseur" : "Nouveau fournisseur"}</DialogTitle>
          <DialogDescription>Coordonnées du fournisseur.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="name">Nom</Label>
            <Input id="name" placeholder="Metro France" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="code">Code (optionnel)</Label>
            <Input id="code" placeholder="METRO" {...register("code")} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="email">Email (optionnel)</Label>
              <Input id="email" type="email" placeholder="contact@metro.fr" {...register("email")} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Téléphone (optionnel)</Label>
              <Input id="phone" placeholder="01 23 45 67 89" {...register("phone")} />
            </div>
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
