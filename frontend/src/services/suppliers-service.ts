import { api } from "@/lib/api";
import type {
  Supplier,
  SupplierPayload,
  SupplierUpdatePayload,
  SupplierPrice,
} from "./types";

export async function listSuppliers(params: { q?: string; limit?: number } = {}) {
  const { data } = await api.get<Supplier[]>("/suppliers/", { params });
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
