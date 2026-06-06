"use client";

import { useMutation } from "@tanstack/react-query";

import { chatWithAI } from "@/services/ai-service";
import type { AIChatMessage } from "@/services/types";

export function useChatAI() {
  return useMutation({
    mutationFn: (vars: { message: string; history: AIChatMessage[] }) =>
      chatWithAI(vars.message, vars.history),
  });
}
