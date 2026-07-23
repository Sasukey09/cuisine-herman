"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  listQuotes,
  getQuote,
  createQuote,
  updateQuote,
  deleteQuote,
  addQuoteLine,
  updateQuoteLine,
  deleteQuoteLine,
  getQuoteComparison,
  orderQuote,
} from "@/services/quotes-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { QuoteCreatePayload, QuoteLinePayload } from "@/services/types";

const KEY = ["quotes"];

export function useQuotes(status?: string) {
  return useQuery({
    queryKey: [...KEY, { status: status ?? "" }],
    queryFn: () => listQuotes(status),
  });
}

export function useQuote(id?: string) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getQuote(id as string),
    enabled: Boolean(id),
  });
}

export function useQuoteComparison(id?: string, enabled = true) {
  return useQuery({
    queryKey: [...KEY, id, "comparison"],
    queryFn: () => getQuoteComparison(id as string),
    enabled: Boolean(id) && enabled,
  });
}

export function useCreateQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuoteCreatePayload) => createQuote(payload),
    onSuccess: (quote) => {
      toast.success(`Devis ${quote.reference ?? ""} créé.`);
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useUpdateQuote(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fields: { title?: string | null; notes?: string | null; status?: string | null }) =>
      updateQuote(id, fields),
    onSuccess: () => {
      toast.success("Devis mis à jour.");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useDeleteQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteQuote(id),
    onSuccess: () => {
      toast.success("Devis supprimé.");
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useAddQuoteLine(quoteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuoteLinePayload) => addQuoteLine(quoteId, payload),
    onSuccess: () => {
      toast.success("Ligne ajoutée.");
      qc.invalidateQueries({ queryKey: [...KEY, quoteId] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useUpdateQuoteLine(quoteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { lineId: string; payload: QuoteLinePayload }) =>
      updateQuoteLine(quoteId, vars.lineId, vars.payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...KEY, quoteId] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useDeleteQuoteLine(quoteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lineId: string) => deleteQuoteLine(quoteId, lineId),
    onSuccess: () => {
      toast.success("Ligne supprimée.");
      qc.invalidateQueries({ queryKey: [...KEY, quoteId] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useOrderQuote(quoteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (supplierId: string) => orderQuote(quoteId, supplierId),
    onSuccess: (quote) => {
      toast.success(
        `Commande passée${quote.supplier_name ? ` chez ${quote.supplier_name}` : ""}.`,
      );
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}
