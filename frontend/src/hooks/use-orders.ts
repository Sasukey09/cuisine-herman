"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  createOrdersFromQuoteLines,
  deleteOrder,
  getOrder,
  getOrderProgress,
  getOrderStatuses,
  listOrders,
  planOrders,
  updateOrder,
} from "@/services/orders-service";
import { getApiErrorMessage } from "@/lib/api-error";

const KEY = ["orders"];

export function useOrders(status?: string, supplierId?: string) {
  return useQuery({
    queryKey: [...KEY, status ?? "all", supplierId ?? "all"],
    queryFn: () => listOrders({ status, supplier_id: supplierId }),
  });
}

export function useOrder(id: string) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getOrder(id),
    enabled: Boolean(id),
  });
}

export function useOrderProgress(id: string) {
  return useQuery({
    queryKey: [...KEY, id, "progress"],
    queryFn: () => getOrderProgress(id),
    enabled: Boolean(id),
  });
}

export function useOrderStatuses() {
  return useQuery({
    queryKey: [...KEY, "statuses"],
    queryFn: getOrderStatuses,
    // Les libellés ne changent qu'avec une livraison du serveur.
    staleTime: 60 * 60 * 1000,
  });
}

/** L'aperçu ne crée rien : il se déclenche à la demande, pas au montage. */
export function usePlanOrders() {
  return useMutation({
    mutationFn: (quoteLineIds: string[]) => planOrders(quoteLineIds),
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}

export function useCreateOrders() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createOrdersFromQuoteLines,
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: KEY });
      // Le nombre de fournisseurs est l'information neuve : c'est ce que
      // l'ancien modèle ne savait pas faire.
      toast.success(
        res.order_count > 1
          ? `${res.order_count} commandes créées chez ${res.supplier_count} fournisseurs`
          : "Commande créée",
      );
    },
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}

export function useUpdateOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...fields }: { id: string; status?: string; expected_date?: string | null; notes?: string | null }) =>
      updateOrder(id, fields),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}

export function useDeleteOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteOrder,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Commande supprimée");
    },
    onError: (err) => toast.error(getApiErrorMessage(err)),
  });
}
