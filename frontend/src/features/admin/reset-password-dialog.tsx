"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

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
import { resetUserPassword } from "@/services/auth-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { Me } from "@/services/types";

interface Props {
  user: Me | null;
  onOpenChange: (open: boolean) => void;
}

export function ResetPasswordDialog({ user, onOpenChange }: Props) {
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (user) setPassword("");
  }, [user]);

  const tooShort = password.length > 0 && password.length < 8;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || password.length < 8) return;
    setPending(true);
    try {
      await resetUserPassword(user.id, password);
      toast.success(
        `Mot de passe réinitialisé. ${user.name || user.email} a été déconnecté de tous ses appareils.`,
      );
      onOpenChange(false);
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={Boolean(user)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Réinitialiser le mot de passe</DialogTitle>
          <DialogDescription>
            Définissez un nouveau mot de passe pour{" "}
            <span className="font-medium text-foreground">{user?.name || user?.email}</span>.
            Communiquez-le-lui directement — il n&apos;est envoyé par aucun email. Toutes ses
            sessions en cours seront fermées.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="new-password">Nouveau mot de passe</Label>
            <Input
              id="new-password"
              type="text"
              autoComplete="off"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8 caractères minimum"
            />
            {tooShort && (
              <p className="text-sm text-destructive">8 caractères minimum.</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={pending || password.length < 8}>
              {pending && <Loader2 className="h-4 w-4 animate-spin" />}
              Réinitialiser
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
