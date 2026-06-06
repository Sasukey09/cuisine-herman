import { api } from "@/lib/api";
import type { AIChatMessage, AIChatResponse } from "./types";

export async function chatWithAI(
  message: string,
  history: AIChatMessage[] = [],
): Promise<AIChatResponse> {
  const { data } = await api.post<AIChatResponse>("/ai/chat", {
    message,
    history,
  });
  return data;
}
