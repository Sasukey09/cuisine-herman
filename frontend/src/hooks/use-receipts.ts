"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  createReceipt,
  deleteReceipt,
  getQualityVocabulary,
  getReceipt,
  getReceiptControl,
  listReceipts,
  prefillFromOrder,
  updateReceipt,
  validateReceipt,
  type ReceiptWrite,
} from "@/services/receipts-service";
import { getApiErrorMessage } from "@/lib/api-error";

const KEY = ["receipts"];

export function useReceipts(params?: { order_id?: string; status?: string }) {
  return useQuery({
    queryKey: [...KEY, params?.order_id ?? "all", params?.status ?? "all"],
    queryFn: () => listReceipts(params),
  });
}

export function useReceipt(id: string) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getReceipt(id),
    enabled: Boolean(id),
  });
}

export function useReceiptControl(id: string) {
  return useQuery({
    queryKey: [...KEY, id, "control"],
    queryFn: () => getReceiptControl(id),
    enabled: Boolean(id),
  });
}

export function useQualityVocabulary() {
  return useQuery({
    queryKey: [...KEY, "quality-checks"],
    queryFn: getQualityVocabulary,
    // Le vocabulaire ne change qu'avec une livraison du serveur.
    staleTime: 60 * 60 * 1000,
  });
}

export function useReceiptPrefill(orderId: string) {
  return useQuery({
    queryKey: [...KEY, "prefill", orderId],
    queryFn: () => prefillFromOrder(orderId),
    enabled: Boolean(orderId),
    // Le restant dû bouge à chaque réception validée : ne pas servir du cache.
    staleTime: 0,
  });
}

export function useCreateReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReceiptWrite) => createReceipt(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}

export function useUpdateReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Partial<ReceiptWrite>) =>
      updateReceipt(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}

export function useValidateReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: validateReceipt,
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: KEY });
      qc.invalidateQueries({ queryKey: ["orders"] });
      const c = res.control;
      // Le message dit ce qui a été constaté, pas seulement « enregistré ».
      if (c.issue_count === 0) {
        toast.success("Réception conforme et validée");
      } else {
        toast.warning(
          `Réception validée · ${c.issue_count} anomalie(s)` +
            (c.missing_value ? ` · ${c.missing_value.toFixed(2)} € manquants` : ""),
        );
      }
    },
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}

export function useDeleteReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteReceipt,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Brouillon supprimé");
    },
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}
