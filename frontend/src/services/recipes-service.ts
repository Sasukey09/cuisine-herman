import { api } from "@/lib/api";
import type {
  Recipe,
  RecipePayload,
  RecipeVersion,
  RecipeVersionPayload,
  ComputeCostRequest,
  RecipeCost,
  RecipeImportStatus,
  RecipeImportSaveRequest,
  RecipeImportSaveResult,
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

/** Upload a recipe PDF → OCR → AI extraction → product matching → cost preview. */
export async function importRecipePdf(file: File): Promise<RecipeImportStatus> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<RecipeImportStatus>("/recipes/import-pdf", form, {
    headers: { "Content-Type": undefined as unknown as string },
  });
  return data;
}

export async function getRecipeImportStatus(jobId: string): Promise<RecipeImportStatus> {
  const { data } = await api.get<RecipeImportStatus>(`/recipes/import-status/${jobId}`);
  return data;
}

/** Validate a preview → create the recipe + version + ingredients + cost. */
export async function saveRecipeImport(
  payload: RecipeImportSaveRequest,
  jobId?: string,
): Promise<RecipeImportSaveResult> {
  const { data } = await api.post<RecipeImportSaveResult>(
    "/recipes/import-save",
    payload,
    { params: jobId ? { job_id: jobId } : undefined },
  );
  return data;
}
