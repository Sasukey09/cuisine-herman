"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  listSuppliers,
  getEnrichedSuppliers,
  getSupplier,
  getSupplierPrices,
  createSupplier,
  updateSupplier,
  deleteSupplier,
} from "@/services/suppliers-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { SupplierPayload, SupplierUpdatePayload } from "@/services/types";

const KEY = ["suppliers"];

export function useSuppliers(q?: string) {
  return useQuery({
    queryKey: [...KEY, { q: q ?? "" }],
    queryFn: () => listSuppliers({ q, limit: 200 }),
  });
}

export function useEnrichedSuppliers(q?: string) {
  return useQuery({
    queryKey: [...KEY, "enriched", { q: q ?? "" }],
    queryFn: () => getEnrichedSuppliers(q || undefined),
  });
}

export function useSupplier(id?: string) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getSupplier(id as string),
    enabled: Boolean(id),
  });
}

export function useSupplierPrices(id?: string) {
  return useQuery({
    queryKey: [...KEY, id, "prices"],
    queryFn: () => getSupplierPrices(id as string),
    enabled: Boolean(id),
  });
}

export function useCreateSupplier() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupplierPayload) => createSupplier(payload),
    onSuccess: () => {
      toast.success("Fournisseur créé");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useUpdateSupplier() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; payload: SupplierUpdatePayload }) =>
      updateSupplier(vars.id, vars.payload),
    onSuccess: () => {
      toast.success("Fournisseur mis à jour");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useDeleteSupplier() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSupplier(id),
    onSuccess: () => {
      toast.success("Fournisseur supprimé");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}
