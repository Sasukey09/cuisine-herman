import { api } from "@/lib/api";
import type {
  AIChatResponse,
  AIConversation,
  AIConversationDetail,
} from "./types";

/**
 * The thread now lives on the server. `history` is no longer sent: it was the
 * only source of truth, so a page reload erased the whole conversation.
 */
export async function chatWithAI(
  message: string,
  conversationId?: string,
): Promise<AIChatResponse> {
  const { data } = await api.post<AIChatResponse>("/ai/chat", {
    message,
    conversation_id: conversationId ?? null,
  });
  return data;
}

export async function listConversations(): Promise<AIConversation[]> {
  const { data } = await api.get<AIConversation[]>("/ai/conversations");
  return data;
}

export async function getConversation(id: string): Promise<AIConversationDetail> {
  const { data } = await api.get<AIConversationDetail>(`/ai/conversations/${id}`);
  return data;
}

export async function deleteConversation(id: string): Promise<void> {
  await api.delete(`/ai/conversations/${id}`);
}

/** Questions worth asking for THIS restaurant, built from its own data. */
export async function getSuggestions(): Promise<string[]> {
  const { data } = await api.get<{ suggestions: string[] }>("/ai/suggestions");
  return data.suggestions;
}
