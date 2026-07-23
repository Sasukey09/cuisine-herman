import { api } from "@/lib/api";
import type {
  Invoice,
  InvoiceLine,
  InvoiceIngestResult,
  InvoiceProcessSummary,
  MapProductResult,
  Product,
  InvoicePreviewResult,
  InvoiceConfirmRequest,
} from "./types";

export async function previewInvoice(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<InvoicePreviewResult>("/invoices/preview", form, {
    headers: { "Content-Type": undefined as unknown as string },
  });
  return data;
}

export async function confirmInvoice(payload: InvoiceConfirmRequest) {
  const { data } = await api.post<InvoiceIngestResult>("/invoices/confirm", payload);
  return data;
}

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

export async function updateInvoice(
  id: string,
  fields: {
    invoice_number?: string | null;
    date?: string | null;
    total_amount?: number | null;
    currency?: string | null;
  },
): Promise<Invoice> {
  const { data } = await api.patch<Invoice>(`/invoices/${id}`, fields);
  return data;
}

export async function deleteInvoice(id: string): Promise<void> {
  await api.delete(`/invoices/${id}`);
}

export async function addInvoiceLine(
  invoiceId: string,
  fields: {
    description?: string | null;
    qty?: number | null;
    unit?: string | null;
    unit_price?: number | null;
    line_total?: number | null;
    product_id?: string | null;
  },
): Promise<InvoiceLine> {
  const { data } = await api.post<InvoiceLine>(`/invoices/${invoiceId}/lines`, fields);
  return data;
}

export async function deleteInvoiceLine(invoiceId: string, lineId: string): Promise<void> {
  await api.delete(`/invoices/${invoiceId}/lines/${lineId}`);
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

export async function createProductFromLine(
  invoiceId: string,
  lineId: string,
  fields: { name?: string | null; sku?: string | null } = {},
): Promise<Product> {
  const { data } = await api.post<Product>(
    `/invoices/${invoiceId}/lines/${lineId}/create-product`,
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
