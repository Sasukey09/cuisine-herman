import { api } from "@/lib/api";
import type { Product, ProductRow, ProductPayload, ProductUpdatePayload } from "./types";

export async function listProducts(params: { q?: string; limit?: number; skip?: number } = {}) {
  const { data } = await api.get<Product[]>("/products/", { params });
  return data;
}

export async function getEnrichedProducts(q?: string) {
  const { data } = await api.get<ProductRow[]>("/products/enriched", {
    params: q ? { q } : undefined,
  });
  return data;
}

export async function listCategories() {
  const { data } = await api.get<string[]>("/products/categories");
  return data;
}

export async function getProduct(id: string) {
  const { data } = await api.get<Product>(`/products/${id}`);
  return data;
}

export async function createProduct(payload: ProductPayload) {
  const { data } = await api.post<Product>("/products/", payload);
  return data;
}

export async function updateProduct(id: string, payload: ProductUpdatePayload) {
  const { data } = await api.put<Product>(`/products/${id}`, payload);
  return data;
}

export async function deleteProduct(id: string) {
  await api.delete(`/products/${id}`);
}
