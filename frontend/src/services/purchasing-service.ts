import { api } from "@/lib/api";
import type {
  ProductPriceHistory,
  SupplierComparison,
  SupplierPurchaseHistory,
  StoredPriceAlert,
  PriceDashboard,
} from "./types";

export async function getProductPriceHistory(productId: string) {
  const { data } = await api.get<ProductPriceHistory>(`/products/${productId}/price-history`);
  return data;
}

export async function getSupplierComparison(productId: string) {
  const { data } = await api.get<SupplierComparison>(`/products/${productId}/supplier-comparison`);
  return data;
}

export async function getSupplierPurchaseHistory(supplierId: string) {
  const { data } = await api.get<SupplierPurchaseHistory>(`/suppliers/${supplierId}/purchase-history`);
  return data;
}

export async function getPriceDashboard() {
  const { data } = await api.get<PriceDashboard>("/dashboard/price-variations");
  return data;
}

export async function getStoredPriceAlerts(unreadOnly = false) {
  const { data } = await api.get<StoredPriceAlert[]>("/alerts/prices", {
    params: unreadOnly ? { unread_only: true } : undefined,
  });
  return data;
}

export async function markPriceAlertRead(alertId: string) {
  await api.post(`/alerts/${alertId}/read`);
}
