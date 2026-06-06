"use client";

import { useRef, useState, useEffect, type FormEvent, type KeyboardEvent } from "react";
import { Bot, User, Send, Loader2, Wrench } from "lucide-react";
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
                  className="rounded-full border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
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
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary/10 text-primary" : "bg-muted text-foreground",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={cn("max-w-[80%] space-y-2", isUser && "items-end")}>
        <div
          className={cn(
            "whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted",
          )}
        >
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
