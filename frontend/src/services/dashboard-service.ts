import { api } from "@/lib/api";
import type {
  CostTrendPoint,
  TopProduct,
  PriceTrendPoint,
  MarginAlert,
  PriceAlert,
  DashboardFilters,
} from "./types";

export async function getCostTrends(
  filters: DashboardFilters & { recipe_id?: string } = {},
): Promise<CostTrendPoint[]> {
  const { data } = await api.get<CostTrendPoint[]>("/dashboard/cost-trends", {
    params: filters,
  });
  return data;
}

export async function getTopProducts(
  params: DashboardFilters & { limit?: number } = {},
): Promise<TopProduct[]> {
  const { data } = await api.get<TopProduct[]>("/dashboard/top-products", { params });
  return data;
}

export async function getPriceTrends(
  productId: string,
  filters: DashboardFilters = {},
): Promise<PriceTrendPoint[]> {
  const { data } = await api.get<PriceTrendPoint[]>("/dashboard/price-trends", {
    params: { product_id: productId, ...filters },
  });
  return data;
}

export async function getMarginAlerts(maxFoodCostPct = 35): Promise<MarginAlert[]> {
  const { data } = await api.get<MarginAlert[]>("/dashboard/margin-alerts", {
    params: { max_food_cost_pct: maxFoodCostPct },
  });
  return data;
}

export async function getPriceAlerts(minIncreasePct = 10): Promise<PriceAlert[]> {
  const { data } = await api.get<PriceAlert[]>("/dashboard/price-alerts", {
    params: { min_increase_pct: minIncreasePct },
  });
  return data;
}
