"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle2, Loader2 } from "lucide-react";

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
import { requestPasswordReset } from "@/services/auth-service";
import { getApiErrorMessage } from "@/lib/api-error";

const schema = z.object({ email: z.string().email("Adresse email invalide") });
type Values = z.infer<typeof schema>;

export function ForgotPasswordForm() {
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  // Calls POST /auth/forgot-password. The backend always answers the same way
  // (a link is sent only if a real password account exists), so we always show
  // the same confirmation — never revealing whether the address has an account.
  const onSubmit = async (values: Values) => {
    setPending(true);
    setError(null);
    try {
      await requestPasswordReset(values.email);
      setSubmitted(true);
    } catch (e) {
      setError(getApiErrorMessage(e, "Impossible d'envoyer le lien. Réessayez."));
    } finally {
      setPending(false);
    }
  };

  if (submitted) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            Vérifiez votre boîte de réception
          </CardTitle>
          <CardDescription>
            Si un compte existe pour cette adresse, un e-mail contenant un lien de
            réinitialisation vient d&apos;être envoyé. Le lien est valable une heure et
            utilisable une seule fois.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button asChild variant="outline" className="w-full">
            <Link href="/login">Retour à la connexion</Link>
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mot de passe oublié</CardTitle>
        <CardDescription>
          Saisissez votre email pour recevoir un lien de réinitialisation.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="vous@restaurant.fr"
              {...register("email")}
            />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          <Button type="submit" variant="gradient" className="w-full" disabled={pending}>
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            Envoyer le lien
          </Button>
          <Button asChild variant="ghost" className="w-full">
            <Link href="/login">Retour à la connexion</Link>
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
