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
import { useCreateUser, useRoles } from "@/hooks/use-admin";

const schema = z.object({
  email: z.string().email("Email invalide"),
  name: z.string().optional(),
  password: z.string().min(8, "8 caractères minimum"),
  role: z.string().min(1, "Rôle requis"),
});

type Values = z.infer<typeof schema>;

export function UserFormDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: roles } = useRoles();
  const create = useCreateUser();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { role: "viewer" },
  });

  useEffect(() => {
    if (open) reset({ email: "", name: "", password: "", role: "viewer" });
  }, [open, reset]);

  const onSubmit = (values: Values) => {
    create.mutate(
      { email: values.email, password: values.password, name: values.name || undefined, role: values.role },
      { onSuccess: () => onOpenChange(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvel utilisateur</DialogTitle>
          <DialogDescription>Ajoutez un membre à votre organisation.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="membre@restaurant.fr" {...register("email")} />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Nom (optionnel)</Label>
            <Input id="name" placeholder="Marie Martin" {...register("name")} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
              {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Rôle</Label>
              <select
                id="role"
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                {...register("role")}
              >
                {(roles ?? ["admin", "manager", "viewer"]).map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              {errors.role && <p className="text-sm text-destructive">{errors.role.message}</p>}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" variant="gradient" disabled={create.isPending}>
              {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Créer l&apos;utilisateur
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
