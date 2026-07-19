"use client";

import { useState } from "react";
import { KeyRound, Plus, Users } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { UserFormDialog } from "./user-form-dialog";
import { ResetPasswordDialog } from "./reset-password-dialog";
import { useUsers } from "@/hooks/use-admin";
import { useAuthStore } from "@/stores/auth-store";
import type { Me } from "@/services/types";

const roleVariant: Record<string, "default" | "secondary" | "outline"> = {
  admin: "default",
  manager: "secondary",
  viewer: "outline",
};

export function UsersTable() {
  const { data: users, isLoading } = useUsers();
  const currentUser = useAuthStore((s) => s.user);
  const [formOpen, setFormOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<Me | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            <Users className="h-4 w-4" />
            Utilisateurs
          </CardTitle>
          <CardDescription>Membres de votre organisation.</CardDescription>
        </div>
        <Button size="sm" variant="gradient" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Ajouter
        </Button>
      </CardHeader>
      <CardContent className="px-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-6">Nom</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Rôles</TableHead>
              <TableHead className="pr-6 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell className="pl-6"><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell className="pr-6"><Skeleton className="h-5 w-24" /></TableCell>
                </TableRow>
              ))
            ) : !users || users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4}>
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    Aucun utilisateur.
                  </p>
                </TableCell>
              </TableRow>
            ) : (
              users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="pl-6 font-medium">
                    {u.name || "—"}
                    {u.id === currentUser?.id && (
                      <span className="ml-2 text-xs text-muted-foreground">(vous)</span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{u.email}</TableCell>
                  <TableCell>
                    <span className="flex flex-wrap gap-1">
                      {u.roles.length ? (
                        u.roles.map((r) => (
                          <Badge key={r} variant={roleVariant[r] ?? "secondary"}>
                            {r}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="pr-6 text-right">
                    {/* The "mot de passe oublié" screen tells the user to ask an
                        admin. Until now an admin had no way to actually do it. */}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setResetTarget(u)}
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                      Mot de passe
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>

      <UserFormDialog open={formOpen} onOpenChange={setFormOpen} />
      <ResetPasswordDialog user={resetTarget} onOpenChange={(o) => !o && setResetTarget(null)} />
    </Card>
  );
}
