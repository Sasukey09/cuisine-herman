"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  chatWithAI,
  deleteConversation,
  getConversation,
  getSuggestions,
  listConversations,
} from "@/services/ai-service";
import { getApiErrorMessage } from "@/lib/api-error";

export function useConversations() {
  return useQuery({
    queryKey: ["ai-conversations"],
    queryFn: listConversations,
  });
}

export function useConversation(id?: string) {
  return useQuery({
    queryKey: ["ai-conversations", id],
    queryFn: () => getConversation(id as string),
    enabled: Boolean(id),
  });
}

/** Suggestions built from this restaurant's own data, not canned filler. */
export function useAiSuggestions() {
  return useQuery({
    queryKey: ["ai-suggestions"],
    queryFn: getSuggestions,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAiChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { message: string; conversationId?: string }) =>
      chatWithAI(vars.message, vars.conversationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ai-conversations"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-conversations"] }),
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
}
