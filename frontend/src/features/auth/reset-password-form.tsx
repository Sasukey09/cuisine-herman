"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle2, Loader2, AlertTriangle } from "lucide-react";

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
import { confirmPasswordReset } from "@/services/auth-service";
import { getApiErrorMessage } from "@/lib/api-error";

// Mirrors the backend policy (security.password_error): >= 8 chars, a letter and
// a digit, plus a client-side "passwords match" check.
const schema = z
  .object({
    password: z
      .string()
      .min(8, "Au moins 8 caractères")
      .regex(/[a-zA-Z]/, "Au moins une lettre")
      .regex(/[0-9]/, "Au moins un chiffre"),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Les mots de passe ne correspondent pas",
  });

type Values = z.infer<typeof schema>;

export function ResetPasswordForm() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";

  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: Values) => {
    setPending(true);
    setError(null);
    try {
      await confirmPasswordReset(token, values.password);
      setDone(true);
      setTimeout(() => router.push("/login"), 2500);
    } catch (e) {
      setError(
        getApiErrorMessage(e, "Lien invalide ou expiré. Refaites une demande de réinitialisation."),
      );
    } finally {
      setPending(false);
    }
  };

  if (!token) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Lien invalide
          </CardTitle>
          <CardDescription>
            Ce lien de réinitialisation est incomplet ou a expiré. Refaites une demande depuis
            l&apos;écran « Mot de passe oublié ».
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button asChild variant="outline" className="w-full">
            <Link href="/forgot-password">Refaire une demande</Link>
          </Button>
        </CardFooter>
      </Card>
    );
  }

  if (done) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            Mot de passe réinitialisé
          </CardTitle>
          <CardDescription>
            Votre mot de passe a été changé. Toutes vos sessions ont été déconnectées par sécurité.
            Redirection vers la connexion…
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button asChild variant="gradient" className="w-full">
            <Link href="/login">Se connecter</Link>
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Nouveau mot de passe</CardTitle>
        <CardDescription>
          Choisissez un nouveau mot de passe (8 caractères minimum, avec une lettre et un chiffre).
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="password">Nouveau mot de passe</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm">Confirmer le mot de passe</Label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              {...register("confirm")}
            />
            {errors.confirm && <p className="text-sm text-destructive">{errors.confirm.message}</p>}
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          <Button type="submit" variant="gradient" className="w-full" disabled={pending}>
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            Réinitialiser le mot de passe
          </Button>
          <Button asChild variant="ghost" className="w-full">
            <Link href="/login">Retour à la connexion</Link>
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
