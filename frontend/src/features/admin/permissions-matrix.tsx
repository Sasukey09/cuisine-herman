"use client";

import { Check, X, ShieldCheck } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Reflects the RBAC actually enforced by the backend (role-name based):
// admin = all, manager = read+write data, viewer = read-only.
const ROLES = ["admin", "manager", "viewer"] as const;

const CAPABILITIES: { label: string; allowed: Record<(typeof ROLES)[number], boolean> }[] = [
  { label: "Consulter (produits, factures, recettes, dashboards)", allowed: { admin: true, manager: true, viewer: true } },
  { label: "Créer / modifier / supprimer les données", allowed: { admin: true, manager: true, viewer: false } },
  { label: "Importer & valider les factures", allowed: { admin: true, manager: true, viewer: false } },
  { label: "Calculer les coûts de recettes", allowed: { admin: true, manager: true, viewer: false } },
  { label: "Gérer les utilisateurs & rôles", allowed: { admin: true, manager: false, viewer: false } },
];

function Cell({ ok }: { ok: boolean }) {
  return ok ? (
    <Check className="mx-auto h-4 w-4 text-emerald-500" />
  ) : (
    <X className="mx-auto h-4 w-4 text-muted-foreground/40" />
  );
}

export function PermissionsMatrix() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="h-4 w-4" />
          Rôles & permissions
        </CardTitle>
        <CardDescription>
          Permissions appliquées par rôle (contrôle d&apos;accès basé sur les rôles).
        </CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-6">Action</TableHead>
              {ROLES.map((r) => (
                <TableHead key={r} className="text-center capitalize">
                  {r}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {CAPABILITIES.map((cap) => (
              <TableRow key={cap.label}>
                <TableCell className="pl-6">{cap.label}</TableCell>
                {ROLES.map((r) => (
                  <TableCell key={r}>
                    <Cell ok={cap.allowed[r]} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
