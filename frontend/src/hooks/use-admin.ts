"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { listUsers, listRoles, createUser } from "@/services/admin-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { CreateUserPayload } from "@/services/types";

export function useUsers() {
  return useQuery({ queryKey: ["admin", "users"], queryFn: listUsers });
}

export function useRoles() {
  return useQuery({ queryKey: ["admin", "roles"], queryFn: listRoles });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateUserPayload) => createUser(payload),
    onSuccess: () => {
      toast.success("Utilisateur créé");
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}
