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
import { ErrorState } from "@/components/error-state";
import { useMe, useLogout } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";
import { RgpdSection } from "@/features/auth/rgpd-section";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 border-b py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function ProfileView() {
  const { data: me, isLoading, isError, error, refetch, isFetching } = useMe();
  const logout = useLogout();
  const isAdmin = useAuthStore((s) => s.hasRole("admin"));

  return (
    <div className="space-y-6">
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Mon profil</CardTitle>
          <CardDescription>Informations de votre compte.</CardDescription>
        </CardHeader>
        <CardContent>
          {isError ? (
            // Never leave the user on a silent, endless skeleton when /me fails
            // for a non-auth reason (5xx / network): say so and offer a retry.
            <ErrorState error={error} onRetry={() => refetch()} retrying={isFetching} compact />
          ) : isLoading || !me ? (
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

              <div className="mt-6 flex items-center justify-end rounded-md bg-muted/50 p-4">
                <Button variant="outline" size="sm" onClick={logout}>
                  <LogOut className="h-4 w-4" />
                  Déconnexion
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* RGPD self-service is admin-scoped (the endpoints are require_admin). */}
      {isAdmin && <RgpdSection />}
    </div>
  );
}
