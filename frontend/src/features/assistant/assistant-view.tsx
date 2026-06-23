"use client";

import { useRef, useState, useEffect, type FormEvent, type KeyboardEvent } from "react";
import { Bot, Send, Loader2, Wrench, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-error";
import { useChatAI } from "@/hooks/use-ai";
import type { AIChatMessage, AIToolCall } from "@/services/types";

interface ChatTurn extends AIChatMessage {
  toolCalls?: AIToolCall[];
}

const SUGGESTIONS = [
  "Quelles recettes ont la marge la plus faible ?",
  "Comment réduire le coût matière de mes recettes les plus chères ?",
  "Quels produits ont le plus augmenté récemment ?",
];

export function AssistantView() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const chat = useChatAI();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, chat.isPending]);

  function send(message: string) {
    const text = message.trim();
    if (!text || chat.isPending) return;

    // History sent to the backend is the prior conversation (roles only).
    const history: AIChatMessage[] = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((prev) => [...prev, { role: "user", content: text }]);
    setInput("");

    chat.mutate(
      { message: text, history },
      {
        onSuccess: (res) => {
          setTurns((prev) => [
            ...prev,
            { role: "assistant", content: res.reply, toolCalls: res.tool_calls },
          ]);
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err));
          // roll back the optimistic user turn so they can retry
          setTurns((prev) => prev.slice(0, -1));
          setInput(text);
        },
      },
    );
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col">
      <PageHeader
        title="Assistant IA"
        description="Posez vos questions de gestion : coûts, marges, optimisations, remplacements d'ingrédients."
      />

      <div
        ref={scrollRef}
        className="mt-2 flex-1 space-y-4 overflow-y-auto rounded-lg border bg-card p-4"
      >
        {turns.length === 0 && !chat.isPending && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <Bot className="h-10 w-10 text-muted-foreground" />
            <p className="max-w-md text-sm text-muted-foreground">
              L&apos;assistant lit vos vraies données (recettes, coûts, prix, alertes) pour
              répondre. Essayez par exemple :
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full bg-secondary px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <MessageBubble key={i} turn={turn} />
        ))}

        {chat.isPending && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            L&apos;assistant réfléchit…
          </div>
        )}
      </div>

      <form onSubmit={onSubmit} className="mt-3 flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Posez votre question… (Entrée pour envoyer, Maj+Entrée pour un saut de ligne)"
          rows={2}
          className={cn(
            "flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm",
            "ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          )}
        />
        <Button type="submit" disabled={chat.isPending || !input.trim()} className="h-10">
          {chat.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          <span className="ml-2 hidden sm:inline">Envoyer</span>
        </Button>
      </form>
    </div>
  );
}

function MessageBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-[14px_14px_4px_14px] bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {turn.content || "—"}
        </div>
      </div>
    );
  }
  return (
    <div className="flex max-w-[84%] gap-2.5">
      <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-lg bg-sidebar text-sidebar-accent">
        <Sparkles className="h-4 w-4" />
      </div>
      <div className="space-y-2">
        <div className="whitespace-pre-wrap rounded-[14px_14px_14px_4px] border bg-card px-4 py-2.5 text-sm">
          {turn.content || "—"}
        </div>
        {turn.toolCalls && turn.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {turn.toolCalls.map((tc, i) => (
              <Badge key={i} variant="secondary" className="gap-1 font-normal">
                <Wrench className="h-3 w-3" />
                {tc.name}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
