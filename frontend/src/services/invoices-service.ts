import { api } from "@/lib/api";
import type {
  Invoice,
  InvoiceLine,
  InvoiceIngestResult,
  InvoiceProcessSummary,
  MapProductResult,
} from "./types";

export async function listInvoices(params: { limit?: number; skip?: number } = {}) {
  const { data } = await api.get<Invoice[]>("/invoices/", { params });
  return data;
}

export async function getInvoice(id: string) {
  const { data } = await api.get<Invoice>(`/invoices/${id}`);
  return data;
}

export async function getInvoiceLines(id: string) {
  const { data } = await api.get<InvoiceLine[]>(`/invoices/${id}/lines`);
  return data;
}

export async function getInvoiceFileUrl(id: string): Promise<string> {
  const { data } = await api.get<{ url: string }>(`/invoices/${id}/file`);
  return data.url;
}

/** Full pipeline: upload -> OCR -> persist lines -> auto-match -> price -> recompute. */
export async function ingestInvoice(file: File): Promise<InvoiceIngestResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<InvoiceIngestResult>("/invoices/ingest", form, {
    // let the browser set the multipart boundary
    headers: { "Content-Type": undefined as unknown as string },
  });
  return data;
}

export async function processInvoice(id: string): Promise<InvoiceProcessSummary> {
  const { data } = await api.post<InvoiceProcessSummary>(`/invoices/${id}/process`);
  return data;
}

export async function updateInvoiceLine(
  invoiceId: string,
  lineId: string,
  fields: {
    description?: string;
    qty?: number | null;
    unit?: string | null;
    unit_price?: number | null;
    line_total?: number | null;
  },
): Promise<InvoiceLine> {
  const { data } = await api.patch<InvoiceLine>(
    `/invoices/${invoiceId}/lines/${lineId}`,
    fields,
  );
  return data;
}

export async function mapLineProduct(
  invoiceId: string,
  lineId: string,
  productId: string,
): Promise<MapProductResult> {
  const { data } = await api.post<MapProductResult>(
    `/invoices/${invoiceId}/lines/${lineId}/map-product`,
    { product_id: productId },
  );
  return data;
}
