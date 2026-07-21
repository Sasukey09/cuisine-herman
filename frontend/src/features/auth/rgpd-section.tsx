"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Loader2, Trash2, AlertTriangle } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { exportOrganizationData, deleteOrganization } from "@/services/rgpd-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { useAuthStore } from "@/stores/auth-store";

/** RGPD self-service, admin-only: data export (art. 15/20) and irreversible
 *  account/organization erasure (art. 17) with a double confirmation. */
export function RgpdSection() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const clearSession = useAuthStore((s) => s.clear);

  const [exporting, setExporting] = useState(false);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onExport = async () => {
    setExporting(true);
    try {
      const data = await exportOrganizationData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `foodgad-donnees-${stamp}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Export téléchargé", {
        description: "Vos données personnelles ont été exportées au format JSON.",
      });
    } catch (e) {
      toast.error("Export impossible", { description: getApiErrorMessage(e) });
    } finally {
      setExporting(false);
    }
  };

  const canDelete = name.trim().length > 0 && password.length > 0 && !deleting;

  const onDelete = async () => {
    setDeleting(true);
    setError(null);
    try {
      await deleteOrganization(name.trim(), password);
      toast.success("Compte supprimé", {
        description: "Votre organisation et toutes ses données ont été définitivement effacées.",
      });
      // The organization no longer exists: drop the local session and any cached
      // data, then send the (now account-less) user to the login screen.
      clearSession();
      queryClient.clear();
      router.replace("/login");
    } catch (e) {
      setError(getApiErrorMessage(e, "Suppression impossible. Vérifiez le nom et le mot de passe."));
      setDeleting(false);
    }
  };

  return (
    <Card className="max-w-2xl border-destructive/30">
      <CardHeader>
        <CardTitle>Mes données (RGPD)</CardTitle>
        <CardDescription>
          Exportez toutes vos données, ou supprimez définitivement votre organisation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium">Exporter mes données</p>
            <p className="text-xs text-muted-foreground">
              Télécharge tout ce que la plateforme détient sur votre organisation (JSON).
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={onExport} disabled={exporting}>
            {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Exporter (JSON)
          </Button>
        </div>

        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4">
          <div className="mb-2 flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm font-semibold">Zone de danger</span>
          </div>
          <p className="mb-3 text-xs text-muted-foreground">
            La suppression est <span className="font-semibold text-foreground">définitive et irréversible</span> :
            toutes vos factures, recettes, produits, prix, comptes et historiques seront effacés. Cette
            action ne peut pas être annulée.
          </p>
          <Button variant="destructive" size="sm" onClick={() => setOpen(true)}>
            <Trash2 className="h-4 w-4" />
            Supprimer définitivement l&apos;organisation
          </Button>
        </div>
      </CardContent>

      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          if (!o) {
            setName("");
            setPassword("");
            setError(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Suppression définitive
            </DialogTitle>
            <DialogDescription>
              Cette action est <span className="font-semibold">irréversible</span>. Toutes les données de
              votre organisation seront effacées et vous serez déconnecté. Pour confirmer, saisissez le
              nom exact de votre organisation et votre mot de passe.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="confirm-name">Nom de l&apos;organisation</Label>
              <Input
                id="confirm-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Nom exact de votre organisation"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Mot de passe</Label>
              <Input
                id="confirm-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={deleting}>
              Annuler
            </Button>
            <Button variant="destructive" onClick={onDelete} disabled={!canDelete}>
              {deleting && <Loader2 className="h-4 w-4 animate-spin" />}
              Supprimer définitivement
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
