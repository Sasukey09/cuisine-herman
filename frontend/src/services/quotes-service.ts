import { api } from "@/lib/api";
import type {
  Quote,
  QuoteDetail,
  QuoteComparison,
  QuoteCreatePayload,
  QuoteLinePayload,
  QuotePreviewResult,
  QuoteConfirmRequest,
  QuoteImportResult,
} from "./types";

export async function listQuotes(status?: string) {
  const { data } = await api.get<Quote[]>("/quotes/", {
    params: status ? { status } : undefined,
  });
  return data;
}

export async function getQuote(id: string) {
  const { data } = await api.get<QuoteDetail>(`/quotes/${id}`);
  return data;
}

export async function createQuote(payload: QuoteCreatePayload) {
  const { data } = await api.post<QuoteDetail>("/quotes/", payload);
  return data;
}

export async function updateQuote(
  id: string,
  fields: { title?: string | null; notes?: string | null; status?: string | null },
) {
  const { data } = await api.patch<QuoteDetail>(`/quotes/${id}`, fields);
  return data;
}

export async function deleteQuote(id: string) {
  await api.delete(`/quotes/${id}`);
}

export async function addQuoteLine(quoteId: string, payload: QuoteLinePayload) {
  const { data } = await api.post<QuoteDetail>(`/quotes/${quoteId}/lines`, payload);
  return data;
}

export async function updateQuoteLine(
  quoteId: string,
  lineId: string,
  payload: QuoteLinePayload,
) {
  const { data } = await api.patch<QuoteDetail>(
    `/quotes/${quoteId}/lines/${lineId}`,
    payload,
  );
  return data;
}

export async function deleteQuoteLine(quoteId: string, lineId: string) {
  const { data } = await api.delete<QuoteDetail>(`/quotes/${quoteId}/lines/${lineId}`);
  return data;
}

export async function getQuoteComparison(id: string) {
  const { data } = await api.get<QuoteComparison>(`/quotes/${id}/comparison`);
  return data;
}

/** Import OCR : aperçu (ne persiste rien) — même pipeline que les factures. */
export async function previewQuote(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<QuotePreviewResult>("/quotes/preview", form, {
    headers: { "Content-Type": undefined as unknown as string },
  });
  return data;
}

/** Import OCR : validation — crée le devis, ses lignes et les produits manquants. */
export async function confirmQuote(payload: QuoteConfirmRequest) {
  const { data } = await api.post<QuoteImportResult>("/quotes/confirm", payload);
  return data;
}

export async function orderQuote(id: string, supplierId: string) {
  const { data } = await api.post<QuoteDetail>(`/quotes/${id}/order`, {
    supplier_id: supplierId,
  });
  return data;
}
