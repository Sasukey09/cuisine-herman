"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin, useRegister } from "@/hooks/use-auth";
import { getApiErrorMessage } from "@/lib/api-error";

const schema = z
  .object({
    org_name: z.string().min(2, "Nom de l'organisation requis"),
    name: z.string().optional(),
    email: z.string().email("Adresse email invalide"),
    password: z.string().min(8, "8 caractères minimum"),
    confirm: z.string(),
  })
  .refine((data) => data.password === data.confirm, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm"],
  });

type RegisterValues = z.infer<typeof schema>;

export function RegisterForm() {
  const router = useRouter();
  const registerMutation = useRegister();
  const login = useLogin();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterValues>({ resolver: zodResolver(schema) });

  const submitting = registerMutation.isPending || login.isPending;

  const onSubmit = async (values: RegisterValues) => {
    try {
      await registerMutation.mutateAsync({
        org_name: values.org_name,
        email: values.email,
        password: values.password,
        name: values.name || undefined,
      });
      // Backend register returns the user (no tokens) -> log in immediately.
      await login.mutateAsync({ email: values.email, password: values.password });
      toast.success("Organisation créée. Bienvenue !");
      router.push("/dashboard");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Inscription impossible"));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Créer une organisation</CardTitle>
        <CardDescription>
          Le premier compte devient administrateur de l&apos;organisation.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="org_name">Organisation</Label>
            <Input id="org_name" placeholder="Mon restaurant" {...register("org_name")} />
            {errors.org_name && <p className="text-sm text-destructive">{errors.org_name.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Votre nom (optionnel)</Label>
            <Input id="name" placeholder="Jean Dupont" {...register("name")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" placeholder="vous@restaurant.fr" {...register("email")} />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
              {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirmation</Label>
              <Input id="confirm" type="password" autoComplete="new-password" {...register("confirm")} />
              {errors.confirm && <p className="text-sm text-destructive">{errors.confirm.message}</p>}
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Créer mon compte
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Déjà un compte ?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Se connecter
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
