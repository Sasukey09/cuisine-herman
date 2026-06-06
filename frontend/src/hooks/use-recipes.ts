"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  listRecipes,
  getRecipe,
  createRecipe,
  getVersion,
  createVersion,
  computeCost,
} from "@/services/recipes-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  RecipePayload,
  RecipeVersionPayload,
  ComputeCostRequest,
} from "@/services/types";

const KEY = ["recipes"];

export function useRecipes() {
  return useQuery({ queryKey: KEY, queryFn: () => listRecipes({ limit: 200 }) });
}

export function useRecipe(id?: string) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getRecipe(id as string),
    enabled: Boolean(id),
  });
}

export function useRecipeVersion(recipeId?: string, versionId?: string | null) {
  return useQuery({
    queryKey: [...KEY, recipeId, "version", versionId],
    queryFn: () => getVersion(recipeId as string, versionId as string),
    enabled: Boolean(recipeId && versionId),
  });
}

export function useCreateRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: RecipePayload) => createRecipe(payload),
    onSuccess: () => {
      toast.success("Recette créée");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useCreateVersion(recipeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: RecipeVersionPayload) => createVersion(recipeId, payload),
    onSuccess: () => {
      toast.success("Fiche technique enregistrée");
      qc.invalidateQueries({ queryKey: [...KEY, recipeId] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useComputeCost(recipeId: string, versionId?: string | null) {
  return useMutation({
    mutationFn: (body: ComputeCostRequest) =>
      computeCost(recipeId, versionId as string, body),
    onError: (e) => toast.error(getApiErrorMessage(e, "Calcul du coût impossible")),
  });
}
