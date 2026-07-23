import { api } from "@/lib/api";
import type {
  OrderPlan,
  OrderStatusOption,
  OrdersCreated,
  PurchaseOrder,
  PurchaseOrderDetail,
  PurchaseOrderProgress,
} from "./types";

export async function listOrders(params?: { status?: string; supplier_id?: string }) {
  const { data } = await api.get<PurchaseOrder[]>("/orders/", { params });
  return data;
}

export async function getOrder(id: string) {
  const { data } = await api.get<PurchaseOrderDetail>(`/orders/${id}`);
  return data;
}

export async function getOrderStatuses() {
  const { data } = await api.get<OrderStatusOption[]>("/orders/statuses");
  return data;
}

export async function getOrderProgress(id: string) {
  const { data } = await api.get<PurchaseOrderProgress>(`/orders/${id}/progress`);
  return data;
}

/** Ce qui SERA commandé, sans rien créer. */
export async function planOrders(quoteLineIds: string[]) {
  const { data } = await api.post<OrderPlan[]>("/orders/plan", {
    quote_line_ids: quoteLineIds,
  });
  return data;
}

/** Les offres retenues deviennent des commandes — une par fournisseur. */
export async function createOrdersFromQuoteLines(payload: {
  quote_line_ids: string[];
  expected_date?: string | null;
  status?: "draft" | "sent";
}) {
  const { data } = await api.post<OrdersCreated>("/orders/from-quote-lines", payload);
  return data;
}

export async function updateOrder(
  id: string,
  fields: { status?: string; expected_date?: string | null; notes?: string | null },
) {
  const { data } = await api.patch<PurchaseOrderDetail>(`/orders/${id}`, fields);
  return data;
}

export async function deleteOrder(id: string) {
  await api.delete(`/orders/${id}`);
}
