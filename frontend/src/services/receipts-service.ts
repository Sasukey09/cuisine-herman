import { api } from "@/lib/api";
import type {
  QualityVocabulary,
  Receipt,
  ReceiptControl,
  ReceiptDetail,
  ReceiptLine,
  ReceiptPrefill,
} from "./types";

export async function listReceipts(params?: { order_id?: string; status?: string }) {
  const { data } = await api.get<Receipt[]>("/receipts/", { params });
  return data;
}

export async function getReceipt(id: string) {
  const { data } = await api.get<ReceiptDetail>(`/receipts/${id}`);
  return data;
}

export async function getReceiptControl(id: string) {
  const { data } = await api.get<ReceiptControl>(`/receipts/${id}/control`);
  return data;
}

export async function getQualityVocabulary() {
  const { data } = await api.get<QualityVocabulary>("/receipts/quality-checks");
  return data;
}

/** Le brouillon d'une commande, pré-rempli avec ce qui reste dû. */
export async function prefillFromOrder(orderId: string) {
  const { data } = await api.get<ReceiptPrefill>(`/receipts/from-order/${orderId}`);
  return data;
}

export interface ReceiptWrite {
  order_id?: string | null;
  supplier_id?: string | null;
  received_at?: string | null;
  delivery_note_number?: string | null;
  device_info?: string | null;
  notes?: string | null;
  lines: ReceiptLine[];
}

export async function createReceipt(payload: ReceiptWrite) {
  const { data } = await api.post<ReceiptDetail>("/receipts/", payload);
  return data;
}

export async function updateReceipt(id: string, payload: Partial<ReceiptWrite>) {
  const { data } = await api.patch<ReceiptDetail>(`/receipts/${id}`, payload);
  return data;
}

/** Fige la réception, écrit les mouvements de stock, avance la commande. */
export async function validateReceipt(id: string) {
  const { data } = await api.post<{ receipt: ReceiptDetail; control: ReceiptControl }>(
    `/receipts/${id}/validate`,
  );
  return data;
}

export async function deleteReceipt(id: string) {
  await api.delete(`/receipts/${id}`);
}
