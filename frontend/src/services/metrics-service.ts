import { api } from "@/lib/api";
import type {
  CustomMetric,
  MetricVariable,
  MetricEvaluationResult,
} from "./types";

export async function listMetrics(): Promise<CustomMetric[]> {
  const { data } = await api.get<CustomMetric[]>("/metrics/");
  return data;
}

export async function getMetricVariables(): Promise<MetricVariable[]> {
  const { data } = await api.get<MetricVariable[]>("/metrics/variables");
  return data;
}

export async function createMetric(payload: {
  name: string;
  formula: string;
  format: string;
  description?: string;
}): Promise<CustomMetric> {
  const { data } = await api.post<CustomMetric>("/metrics/", payload);
  return data;
}

export async function deleteMetric(id: string): Promise<void> {
  await api.delete(`/metrics/${id}`);
}

export async function evaluateRecipeMetrics(
  recipeId: string,
  sellingPrice?: number,
): Promise<MetricEvaluationResult> {
  const { data } = await api.get<MetricEvaluationResult>(
    `/metrics/evaluate/recipe/${recipeId}`,
    { params: sellingPrice != null ? { selling_price: sellingPrice } : {} },
  );
  return data;
}
