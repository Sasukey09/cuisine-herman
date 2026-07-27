import { api } from "@/lib/api";
import type {
  Supplier,
  SupplierRow,
  SupplierPayload,
  SupplierUpdatePayload,
  SupplierPrice,
} from "./types";

export async function listSuppliers(params: { q?: string; limit?: number } = {}) {
  const { data } = await api.get<Supplier[]>("/suppliers/", { params });
  return data;
}

export async function getEnrichedSuppliers(q?: string) {
  const { data } = await api.get<SupplierRow[]>("/suppliers/enriched", {
    params: q ? { q } : undefined,
  });
  return data;
}

export async function getSupplier(id: string) {
  const { data } = await api.get<Supplier>(`/suppliers/${id}`);
  return data;
}

export async function getSupplierPrices(id: string) {
  const { data } = await api.get<SupplierPrice[]>(`/suppliers/${id}/prices`);
  return data;
}

export async function createSupplier(payload: SupplierPayload) {
  const { data } = await api.post<Supplier>("/suppliers/", payload);
  return data;
}

export async function updateSupplier(id: string, payload: SupplierUpdatePayload) {
  const { data } = await api.put<Supplier>(`/suppliers/${id}`, payload);
  return data;
}

export async function deleteSupplier(id: string) {
  await api.delete(`/suppliers/${id}`);
}

export interface SupplierOverview {
  supplier_id: string;
  supplier_name: string;
  rating?: number | null;
  order_count: number;
  quote_count: number;
  invoice_count: number;
  receipt_count: number;
  ordered_total: number;
  billed_total: number;
  annual_amount: number;
  monthly: Array<{ month: string; amount: number }>;
  top_products: Array<{ product_id: string; product_name?: string | null; amount: number; count: number }>;
  distinct_products: number;
  conformity_rate?: number | null;
  on_time_rate?: number | null;
  late_count: number;
  /** null tant qu'aucune réception ne permet de juger — jamais inventé. */
  score?: number | null;
  score_basis: { conformity?: number | null; punctuality?: number | null; receipts_judged: number };
  price_trend_pct?: number | null;
  orders_by_status: Record<string, number>;
  savings: {
    realized: number;
    missed: number;
    possible: number;
    best_choice_rate: number | null;
    compared_lines: number;
    labels: { realized: string; missed: string; possible: string; best_choice_rate: string };
  };
}

export async function getSupplierOverview(id: string) {
  const { data } = await api.get<SupplierOverview>(`/suppliers/${id}/overview`);
  return data;
}
