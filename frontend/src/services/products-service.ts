import { api } from "@/lib/api";
import type {
  Product,
  ProductRow,
  ProductPayload,
  ProductUpdatePayload,
  ProductSuppliersResponse,
  ProductSupplierPayload,
  ProductSupplierUpdatePayload,
  ProductSupplierRow,
  ProductInvoiceRow,
  ProductRecipeRow,
} from "./types";

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

// --- Product detail tabs (Phase 2) ----------------------------------------

export async function getProductSuppliers(id: string) {
  const { data } = await api.get<ProductSuppliersResponse>(`/products/${id}/suppliers`);
  return data;
}

export async function addProductSupplier(id: string, payload: ProductSupplierPayload) {
  const { data } = await api.post<ProductSupplierRow>(`/products/${id}/suppliers`, payload);
  return data;
}

export async function updateProductSupplier(
  id: string,
  linkId: string,
  payload: ProductSupplierUpdatePayload,
) {
  const { data } = await api.patch<ProductSupplierRow>(
    `/products/${id}/suppliers/${linkId}`,
    payload,
  );
  return data;
}

export async function deleteProductSupplier(id: string, linkId: string) {
  await api.delete(`/products/${id}/suppliers/${linkId}`);
}

export async function getProductInvoices(id: string) {
  const { data } = await api.get<{ product_id: string; invoices: ProductInvoiceRow[] }>(
    `/products/${id}/invoices`,
  );
  return data.invoices;
}

export async function getProductRecipes(id: string) {
  const { data } = await api.get<{ product_id: string; recipes: ProductRecipeRow[] }>(
    `/products/${id}/recipes`,
  );
  return data.recipes;
}

// --- Fiche produit 360° (Phase 3) -----------------------------------------

export interface ProductOverview {
  product_id: string;
  product_name: string;
  category: string | null;
  unit_code: string | null;
  annual_amount: number;
  monthly: Array<{ month: string; amount: number }>;
  purchase_count: number;
  supplier_count: number;
  recipe_count: number;
  offer_count: number;
  cheapest_supplier: { supplier_id: string; supplier_name: string | null; cost: number | null } | null;
  last_cost: number | null;
  avg_cost: number | null;
  best_cost: number | null;
  price_trend_pct: number | null;
  offers: {
    best_price: number | null;
    best_supplier_name: string | null;
    latest_price: number | null;
    avg_price: number | null;
    supplier_count: number;
  } | null;
  savings: {
    realized: number;
    missed: number;
    possible: number;
    best_choice_rate: number | null;
    compared_lines: number;
    labels: { realized: string; missed: string; possible: string; best_choice_rate: string };
  };
  top_suppliers: Array<{
    supplier_id: string;
    supplier_name: string | null;
    amount: number;
    count: number;
    is_cheapest: boolean;
  }>;
}

export async function getProductOverview(id: string) {
  const { data } = await api.get<ProductOverview>(`/products/${id}/overview`);
  return data;
}
