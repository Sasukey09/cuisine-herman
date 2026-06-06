"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listMetrics,
  getMetricVariables,
  createMetric,
  deleteMetric,
  evaluateRecipeMetrics,
} from "@/services/metrics-service";

const KEY = ["metrics"];

export function useMetrics() {
  return useQuery({ queryKey: KEY, queryFn: listMetrics });
}

export function useMetricVariables() {
  return useQuery({ queryKey: [...KEY, "variables"], queryFn: getMetricVariables });
}

export function useCreateMetric() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createMetric,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteMetric() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteMetric,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useEvaluateRecipeMetrics(recipeId?: string, sellingPrice?: number) {
  return useQuery({
    queryKey: [...KEY, "evaluate", recipeId, sellingPrice],
    queryFn: () => evaluateRecipeMetrics(recipeId as string, sellingPrice),
    enabled: Boolean(recipeId),
  });
}
