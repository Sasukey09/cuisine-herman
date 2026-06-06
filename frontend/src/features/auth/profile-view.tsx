"use client";

import { LogOut } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe, useLogout } from "@/hooks/use-auth";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 border-b py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function ProfileView() {
  const { data: me, isLoading } = useMe();
  const logout = useLogout();

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Mon profil</CardTitle>
        <CardDescription>Informations de votre compte.</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading || !me ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-2/3" />
          </div>
        ) : (
          <>
            <Row label="Nom" value={me.name || "—"} />
            <Row label="Email" value={me.email} />
            <Row
              label="Rôles"
              value={
                <span className="flex flex-wrap gap-1">
                  {me.roles.length
                    ? me.roles.map((r) => (
                        <Badge key={r} variant="secondary">
                          {r}
                        </Badge>
                      ))
                    : "—"}
                </span>
              }
            />
            <Row label="Organisation (ID)" value={<code className="text-xs">{me.tenant_id}</code>} />

            <div className="mt-6 flex items-center justify-between rounded-md bg-muted/50 p-4">
              <p className="text-xs text-muted-foreground">
                La modification du nom et du mot de passe nécessitera des endpoints
                backend dédiés (à venir).
              </p>
              <Button variant="outline" size="sm" onClick={logout}>
                <LogOut className="h-4 w-4" />
                Déconnexion
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
