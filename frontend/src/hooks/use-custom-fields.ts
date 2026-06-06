"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listFields,
  createField,
  deleteField,
  getEntityValues,
  setEntityValues,
} from "@/services/custom-fields-service";

const KEY = ["custom-fields"];

export function useCustomFields(target?: string) {
  return useQuery({
    queryKey: [...KEY, "defs", target ?? "all"],
    queryFn: () => listFields(target),
  });
}

export function useCreateField() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createField,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteField() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteField,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useEntityValues(target?: string, entityId?: string) {
  return useQuery({
    queryKey: [...KEY, "values", target, entityId],
    queryFn: () => getEntityValues(target as string, entityId as string),
    enabled: Boolean(target && entityId),
  });
}

export function useSetEntityValues() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { target: string; entityId: string; values: Record<string, unknown> }) =>
      setEntityValues(vars.target, vars.entityId, vars.values),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...KEY, "values"] }),
  });
}
