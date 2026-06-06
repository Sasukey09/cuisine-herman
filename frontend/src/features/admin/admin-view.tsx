"use client";

import { ShieldAlert } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { UsersTable } from "./users-table";
import { PermissionsMatrix } from "./permissions-matrix";
import { useAuthStore } from "@/stores/auth-store";

export function AdminView() {
  const isAdmin = useAuthStore((s) => s.hasRole("admin"));

  if (!isAdmin) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-12 text-center text-sm text-muted-foreground">
          <ShieldAlert className="h-8 w-8 text-amber-500" />
          Accès réservé aux administrateurs.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <UsersTable />
      <PermissionsMatrix />
    </div>
  );
}
