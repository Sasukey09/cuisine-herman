"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ClipboardList, Loader2 } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useQuotes, useCreateQuote } from "@/hooks/use-quotes";
import { useProducts } from "@/hooks/use-products";
import { useAuthStore } from "@/stores/auth-store";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Quote, QuoteStatus } from "@/services/types";

const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

export function statusBadge(status?: string | null) {
  const s = (status ?? "draft") as QuoteStatus;
  if (s === "ordered") return <Badge variant="success">Commandé</Badge>;
  if (s === "archived") return <Badge variant="outline">Archivé</Badge>;
  return <Badge variant="warning">Brouillon</Badge>;
}

interface DraftLine {
  product_id: string;
  qty: string;
}

export function QuotesView() {
  const router = useRouter();
  const { data: quotes, isLoading } = useQuotes();
  const hasRole = useAuthStore((s) => s.hasRole);
  const canWrite = hasRole("admin", "manager");
  const [open, setOpen] = useState(false);

  return (
    <>
      <PageHeader
        title="Devis"
        description="Comparez vos fournisseurs sur un panier de produits, puis commandez au meilleur."
        action={
          canWrite ? (
            <Button variant="gradient" onClick={() => setOpen(true)}>
              <Plus /> Nouveau devis
            </Button>
          ) : null
        }
      />

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Chargement…</p>
      ) : !quotes || quotes.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <ClipboardList className="h-8 w-8 text-muted-foreground" />
            <div>
              <p className="font-medium">Aucun devis pour le moment.</p>
              <p className="text-sm text-muted-foreground">
                Créez un devis pour comparer les prix de vos fournisseurs.
              </p>
            </div>
            {canWrite ? (
              <Button variant="gradient" onClick={() => setOpen(true)}>
                <Plus /> Nouveau devis
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {quotes.map((q) => (
            <QuoteCard key={q.id} quote={q} onOpen={() => router.push(`/devis/${q.id}`)} />
          ))}
        </div>
      )}

      {canWrite ? (
        <CreateQuoteDialog open={open} onOpenChange={setOpen} />
      ) : null}
    </>
  );
}

function QuoteCard({ quote, onOpen }: { quote: Quote; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="w-full rounded-xl border border-border/60 bg-card p-4 text-left transition-colors hover:border-border hover:bg-accent/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-serif text-[15px] font-semibold">
              {quote.title?.trim() || quote.reference || "Devis"}
            </span>
            {statusBadge(quote.status)}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {quote.reference}
            {quote.line_count != null ? ` · ${quote.line_count} ligne(s)` : ""}
            {quote.supplier_name ? ` · ${quote.supplier_name}` : ""}
            {quote.created_at ? ` · ${formatDate(quote.created_at)}` : ""}
          </p>
        </div>
        {quote.total_amount != null ? (
          <div className="shrink-0 text-right">
            <div className="text-sm font-semibold">{formatCurrency(quote.total_amount)}</div>
            <div className="text-[11px] text-muted-foreground">total retenu</div>
          </div>
        ) : null}
      </div>
    </button>
  );
}

function CreateQuoteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const { data: products } = useProducts();
  const create = useCreateQuote();
  const [title, setTitle] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([{ product_id: "", qty: "" }]);

  function reset() {
    setTitle("");
    setLines([{ product_id: "", qty: "" }]);
  }

  function submit() {
    const payloadLines = lines
      .filter((l) => l.product_id)
      .map((l) => ({
        product_id: l.product_id,
        qty: l.qty.trim() === "" ? null : Number(l.qty.replace(",", ".")),
      }));
    create.mutate(
      { title: title.trim() || null, lines: payloadLines },
      {
        onSuccess: (quote) => {
          onOpenChange(false);
          reset();
          router.push(`/devis/${quote.id}`);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau devis</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="quote-title">Intitulé</Label>
            <Input
              id="quote-title"
              placeholder="Réappro janvier"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label>Produits à comparer</Label>
            {lines.map((line, i) => (
              <div key={i} className="flex items-center gap-2">
                <select
                  className={SELECT_CLASS}
                  value={line.product_id}
                  onChange={(e) => {
                    const next = [...lines];
                    next[i] = { ...next[i], product_id: e.target.value };
                    setLines(next);
                  }}
                >
                  <option value="">— produit —</option>
                  {(products ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <Input
                  className="w-24"
                  inputMode="decimal"
                  placeholder="Qté"
                  value={line.qty}
                  onChange={(e) => {
                    const next = [...lines];
                    next[i] = { ...next[i], qty: e.target.value };
                    setLines(next);
                  }}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="shrink-0"
                  onClick={() => setLines(lines.filter((_, j) => j !== i))}
                  disabled={lines.length === 1}
                  aria-label="Retirer la ligne"
                >
                  <Trash2 className="text-muted-foreground" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setLines([...lines, { product_id: "", qty: "" }])}
            >
              <Plus /> Ajouter un produit
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button
            variant="gradient"
            onClick={submit}
            disabled={create.isPending || !lines.some((l) => l.product_id)}
          >
            {create.isPending ? <Loader2 className="animate-spin" /> : null}
            Créer le devis
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
