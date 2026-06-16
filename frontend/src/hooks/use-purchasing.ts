"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  getProductPriceHistory,
  getSupplierComparison,
  getSupplierPurchaseHistory,
  getPriceDashboard,
  getStoredPriceAlerts,
  markPriceAlertRead,
} from "@/services/purchasing-service";
import { getApiErrorMessage } from "@/lib/api-error";

export function useProductPriceHistory(productId?: string) {
  return useQuery({
    queryKey: ["price-history", productId],
    queryFn: () => getProductPriceHistory(productId as string),
    enabled: Boolean(productId),
  });
}

export function useSupplierComparison(productId?: string) {
  return useQuery({
    queryKey: ["supplier-comparison", productId],
    queryFn: () => getSupplierComparison(productId as string),
    enabled: Boolean(productId),
  });
}

export function useSupplierPurchaseHistory(supplierId?: string) {
  return useQuery({
    queryKey: ["supplier-purchases", supplierId],
    queryFn: () => getSupplierPurchaseHistory(supplierId as string),
    enabled: Boolean(supplierId),
  });
}

export function usePriceDashboard() {
  return useQuery({ queryKey: ["price-dashboard"], queryFn: getPriceDashboard });
}

export function useStoredPriceAlerts(unreadOnly = false) {
  return useQuery({
    queryKey: ["stored-price-alerts", unreadOnly],
    queryFn: () => getStoredPriceAlerts(unreadOnly),
  });
}

export function useMarkPriceAlertRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => markPriceAlertRead(alertId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["stored-price-alerts"] }),
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}
