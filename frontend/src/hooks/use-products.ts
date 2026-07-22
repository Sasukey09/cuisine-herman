"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  listProducts,
  getEnrichedProducts,
  getProduct,
  createProduct,
  updateProduct,
  deleteProduct,
  listCategories,
} from "@/services/products-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { ProductPayload, ProductUpdatePayload } from "@/services/types";

const KEY = ["products"];

export function useProducts(q?: string) {
  return useQuery({
    queryKey: [...KEY, { q: q ?? "" }],
    queryFn: () => listProducts({ q, limit: 200 }),
  });
}

export function useEnrichedProducts(q?: string) {
  return useQuery({
    queryKey: [...KEY, "enriched", { q: q ?? "" }],
    queryFn: () => getEnrichedProducts(q || undefined),
  });
}

export function useProduct(id?: string) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getProduct(id as string),
    enabled: Boolean(id),
  });
}

export function useProductCategories() {
  return useQuery({
    queryKey: ["product-categories"],
    queryFn: listCategories,
    staleTime: 60 * 60 * 1000, // the taxonomy is effectively static
  });
}

export function useCreateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductPayload) => createProduct(payload),
    onSuccess: () => {
      toast.success("Produit créé");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useUpdateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; payload: ProductUpdatePayload }) =>
      updateProduct(vars.id, vars.payload),
    onSuccess: () => {
      toast.success("Produit mis à jour");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useDeleteProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteProduct(id),
    onSuccess: () => {
      toast.success("Produit supprimé");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}
