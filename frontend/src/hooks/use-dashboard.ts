"use client";

import { useQuery } from "@tanstack/react-query";

import {
  getCostTrends,
  getTopProducts,
  getMarginAlerts,
  getPriceAlerts,
  getPriceTrends,
} from "@/services/dashboard-service";
import type { DashboardFilters } from "@/services/types";

export function useCostTrends(filters: DashboardFilters & { recipe_id?: string } = {}) {
  return useQuery({
    queryKey: ["dashboard", "cost-trends", filters],
    queryFn: () => getCostTrends(filters),
  });
}

export function useTopProducts(params: DashboardFilters & { limit?: number } = {}) {
  return useQuery({
    queryKey: ["dashboard", "top-products", params],
    queryFn: () => getTopProducts(params),
  });
}

export function useMarginAlerts(maxFoodCostPct = 35) {
  return useQuery({
    queryKey: ["dashboard", "margin-alerts", maxFoodCostPct],
    queryFn: () => getMarginAlerts(maxFoodCostPct),
  });
}

export function usePriceAlerts(minIncreasePct = 10) {
  return useQuery({
    queryKey: ["dashboard", "price-alerts", minIncreasePct],
    queryFn: () => getPriceAlerts(minIncreasePct),
  });
}

export function usePriceTrends(productId?: string, filters: DashboardFilters = {}) {
  return useQuery({
    queryKey: ["dashboard", "price-trends", productId, filters],
    queryFn: () => getPriceTrends(productId as string, filters),
    enabled: Boolean(productId),
  });
}
