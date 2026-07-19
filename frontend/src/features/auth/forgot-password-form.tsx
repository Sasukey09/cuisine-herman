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

const schema = z.object({ email: z.string().email("Adresse email invalide") });
type Values = z.infer<typeof schema>;

export function ForgotPasswordForm() {
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  // NOTE: the backend has no /auth/forgot-password endpoint yet. This UI is
  // wired and ready; once the endpoint exists, replace the timeout with the
  // real API call (auth-service.requestPasswordReset).
  // There is no mail provider, so no reset link can be sent. This screen used to
  // fake a 600 ms delay and then claim "check your emails" — the user waited for
  // a message that would never arrive. Tell the truth, and point to the one path
  // that actually works (an admin can now reset a password).
  const onSubmit = async () => {
    setPending(true);
    await new Promise((r) => setTimeout(r, 200));
    setPending(false);
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            Demandez à votre administrateur
          </CardTitle>
          <CardDescription>
            La réinitialisation par email n&apos;est pas encore disponible. L&apos;administrateur
            de votre établissement peut vous définir un nouveau mot de passe depuis l&apos;écran
            <span className="font-medium text-foreground"> Administration</span>.
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
            <Input id="email" type="email" autoComplete="email" placeholder="vous@restaurant.fr" {...register("email")} />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
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
