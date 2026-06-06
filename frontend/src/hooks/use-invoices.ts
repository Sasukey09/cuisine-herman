"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  listInvoices,
  getInvoice,
  getInvoiceLines,
  ingestInvoice,
  processInvoice,
  mapLineProduct,
  updateInvoiceLine,
} from "@/services/invoices-service";
import { getApiErrorMessage } from "@/lib/api-error";

const KEY = ["invoices"];

export function useInvoices() {
  return useQuery({ queryKey: KEY, queryFn: () => listInvoices({ limit: 200 }) });
}

export function useInvoice(id?: string) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getInvoice(id as string),
    enabled: Boolean(id),
  });
}

export function useInvoiceLines(id?: string) {
  return useQuery({
    queryKey: [...KEY, id, "lines"],
    queryFn: () => getInvoiceLines(id as string),
    enabled: Boolean(id),
  });
}

export function useIngestInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => ingestInvoice(file),
    onSuccess: (res) => {
      toast.success(
        `Facture traitée : ${res.summary.lines} ligne(s), ${res.summary.matched} associée(s).`,
      );
      qc.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Échec du traitement de la facture")),
  });
}

export function useMapLineProduct(invoiceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { lineId: string; productId: string }) =>
      mapLineProduct(invoiceId, vars.lineId, vars.productId),
    onSuccess: () => {
      toast.success("Ligne associée au produit");
      qc.invalidateQueries({ queryKey: [...KEY, invoiceId] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useUpdateInvoiceLine(invoiceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      lineId: string;
      fields: {
        description?: string;
        qty?: number | null;
        unit?: string | null;
        unit_price?: number | null;
        line_total?: number | null;
      };
    }) => updateInvoiceLine(invoiceId, vars.lineId, vars.fields),
    onSuccess: () => {
      toast.success("Ligne corrigée");
      qc.invalidateQueries({ queryKey: [...KEY, invoiceId] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useProcessInvoice(invoiceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => processInvoice(invoiceId),
    onSuccess: (summary) => {
      toast.success(`Re-traitement : ${summary.matched} ligne(s) associée(s).`);
      qc.invalidateQueries({ queryKey: [...KEY, invoiceId] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}
