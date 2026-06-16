"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  listRecipes,
  getRecipe,
  createRecipe,
  updateRecipe,
  deleteRecipe,
  getVersion,
  createVersion,
  computeCost,
  importRecipePdf,
  saveRecipeImport,
} from "@/services/recipes-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  RecipePayload,
  RecipeVersionPayload,
  ComputeCostRequest,
  RecipeImportSaveRequest,
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

export function useUpdateRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; payload: RecipePayload }) =>
      updateRecipe(vars.id, vars.payload),
    onSuccess: () => {
      toast.success("Recette modifiée");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useDeleteRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteRecipe(id),
    onSuccess: () => {
      toast.success("Recette supprimée");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Suppression impossible")),
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

export function useImportRecipePdf() {
  return useMutation({
    mutationFn: (file: File) => importRecipePdf(file),
    onError: (e) => toast.error(getApiErrorMessage(e, "Échec de l'import du PDF")),
  });
}

export function useSaveRecipeImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { payload: RecipeImportSaveRequest; jobId?: string }) =>
      saveRecipeImport(vars.payload, vars.jobId),
    onSuccess: () => {
      toast.success("Fiche enregistrée et chiffrée");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Échec de l'enregistrement")),
  });
}

export function useComputeCost(recipeId: string, versionId?: string | null) {
  return useMutation({
    mutationFn: (body: ComputeCostRequest) =>
      computeCost(recipeId, versionId as string, body),
    onError: (e) => toast.error(getApiErrorMessage(e, "Calcul du coût impossible")),
  });
}
