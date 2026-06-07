import { api } from "@/lib/api";
import type {
  Recipe,
  RecipePayload,
  RecipeVersion,
  RecipeVersionPayload,
  ComputeCostRequest,
  RecipeCost,
} from "./types";

export async function listRecipes(params: { limit?: number; skip?: number } = {}) {
  const { data } = await api.get<Recipe[]>("/recipes/", { params });
  return data;
}

export async function getRecipe(id: string) {
  const { data } = await api.get<Recipe>(`/recipes/${id}`);
  return data;
}

export async function createRecipe(payload: RecipePayload) {
  const { data } = await api.post<Recipe>("/recipes/", payload);
  return data;
}

export async function updateRecipe(id: string, payload: RecipePayload) {
  const { data } = await api.put<Recipe>(`/recipes/${id}`, payload);
  return data;
}

export async function deleteRecipe(id: string) {
  await api.delete(`/recipes/${id}`);
}

export async function getVersion(recipeId: string, versionId: string) {
  const { data } = await api.get<RecipeVersion>(`/recipes/${recipeId}/versions/${versionId}`);
  return data;
}

export async function createVersion(recipeId: string, payload: RecipeVersionPayload) {
  const { data } = await api.post<RecipeVersion>(`/recipes/${recipeId}/versions`, payload);
  return data;
}

export async function computeCost(
  recipeId: string,
  versionId: string,
  body: ComputeCostRequest,
) {
  const { data } = await api.post<RecipeCost>(
    `/recipes/${recipeId}/versions/${versionId}/compute-cost`,
    body,
  );
  return data;
}
