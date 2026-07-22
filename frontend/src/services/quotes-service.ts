import { api } from "@/lib/api";
import type {
  Quote,
  QuoteDetail,
  QuoteComparison,
  QuoteCreatePayload,
  QuoteLinePayload,
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

export async function orderQuote(id: string, supplierId: string) {
  const { data } = await api.post<QuoteDetail>(`/quotes/${id}/order`, {
    supplier_id: supplierId,
  });
  return data;
}
