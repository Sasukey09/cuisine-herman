"use client";

import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import { Loader2, Wand2, Plus, Trash2, CheckCircle2, Youtube, AlertTriangle, Upload } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { BackButton } from "@/components/back-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getApiErrorMessage } from "@/lib/api-error";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { useExtractVideo, useExtractVideoFile, useSaveVideoRecipe } from "@/hooks/use-video";
import type { VideoExtractResult, VideoIngredientDraft, VideoSaveResult } from "@/services/types";

interface Row extends VideoIngredientDraft {}

/** Extract a YouTube video id from a watch / youtu.be / shorts / embed URL. */
function youtubeEmbedId(raw: string): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw.trim());
    const host = u.hostname.replace(/^www\./, "");
    if (host === "youtu.be") return u.pathname.slice(1).split("/")[0] || null;
    if (host.endsWith("youtube.com")) {
      if (u.pathname === "/watch") return u.searchParams.get("v");
      const m = u.pathname.match(/^\/(?:shorts|embed)\/([^/?]+)/);
      if (m) return m[1];
    }
  } catch {
    /* not a URL yet */
  }
  return null;
}

export function VideoImportView() {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [portions, setPortions] = useState<string>("");
  const [rows, setRows] = useState<Row[]>([]);
  const [stepsText, setStepsText] = useState("");
  const [hasDraft, setHasDraft] = useState(false);
  const [saved, setSaved] = useState<VideoSaveResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const extract = useExtractVideo();
  const extractFile = useExtractVideoFile();
  const save = useSaveVideoRecipe();

  function loadDraft(res: VideoExtractResult) {
    setName(res.draft.name);
    setPortions(res.draft.yield_qty ? String(res.draft.yield_qty) : "");
    setRows(res.draft.ingredients ?? []);
    setStepsText((res.draft.steps ?? []).join("\n"));
    setHasDraft(true);
    toast.success("Recette extraite — vérifiez les quantités estimées.");
  }

  function onExtract(e: FormEvent) {
    e.preventDefault();
    const link = url.trim();
    if (!link || extract.isPending) return;
    setSaved(null);
    extract.mutate(link, {
      onSuccess: loadDraft,
      onError: (err) => toast.error(getApiErrorMessage(err)),
    });
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || extractFile.isPending) return;
    setSaved(null);
    toast.message("Analyse du fichier… (transcription audio, peut prendre 1–2 min)");
    extractFile.mutate(file, {
      onSuccess: loadDraft,
      onError: (err) => toast.error(getApiErrorMessage(err)),
    });
  }

  function updateRow(i: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((prev) => [...prev, { name: "", qty: null, unit: "" }]);
  }
  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, idx) => idx !== i));
  }

  function onSave() {
    if (!name.trim()) {
      toast.error("Donnez un nom à la recette.");
      return;
    }
    const ingredients = rows
      .filter((r) => r.name.trim())
      .map((r) => ({
        name: r.name.trim(),
        qty: r.qty === null || (r.qty as unknown) === "" ? null : Number(r.qty),
        unit: r.unit?.trim() || null,
      }));
    const steps = stepsText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    save.mutate(
      { name: name.trim(), yield_qty: portions ? Number(portions) : null, ingredients, steps },
      {
        onSuccess: (res) => {
          setSaved(res);
          toast.success("Fiche enregistrée et chiffrée.");
        },
        onError: (err) => toast.error(getApiErrorMessage(err)),
      },
    );
  }

  return (
    <>
      <BackButton />
      <PageHeader
        title="Import depuis une vidéo"
        description="Collez un lien (YouTube, TikTok, Instagram, Facebook…) OU importez un fichier vidéo. L'IA en extrait une fiche recette modifiable, puis la chiffre avec vos prix."
      />

      <form onSubmit={onExtract} className="flex flex-col gap-2 sm:flex-row">
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=…"
          className="flex-1"
        />
        <Button type="submit" variant="gradient" disabled={extract.isPending || !url.trim()}>
          {extract.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Wand2 className="h-4 w-4" />
          )}
          <span className="ml-2">Analyser</span>
        </Button>
      </form>

      <div className="mt-2 flex items-center gap-3">
        <input
          ref={fileRef}
          type="file"
          accept="video/*,audio/*"
          className="hidden"
          onChange={onFile}
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => fileRef.current?.click()}
          disabled={extractFile.isPending}
        >
          {extractFile.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          <span className="ml-2">Importer un fichier vidéo</span>
        </Button>
        <span className="text-xs text-muted-foreground">
          Alternative fiable si le lien est bloqué (transcription audio, ~1–2 min).
        </span>
      </div>

      {youtubeEmbedId(url) && (
        <Card className="mt-3">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Youtube className="h-4 w-4 text-red-500" />
              Aperçu de la vidéo
            </CardTitle>
            <CardDescription>
              Visionnez la vidéo ici. Pour générer la fiche : « Analyser » (si le lien est
              accessible) ou « Importer un fichier vidéo ».
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="aspect-video w-full overflow-hidden rounded-md border">
              <iframe
                className="h-full w-full"
                src={`https://www.youtube.com/embed/${youtubeEmbedId(url)}`}
                title="Aperçu vidéo"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            </div>
          </CardContent>
        </Card>
      )}

      {extract.data && (
        <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Youtube className="h-3.5 w-3.5" />
          Source : {extract.data.platform} · transcription :{" "}
          {extract.data.transcript_source === "youtube_captions" ? "sous-titres" : "audio (STT)"}
        </p>
      )}

      {hasDraft && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">Fiche extraite (modifiable)</CardTitle>
            <CardDescription className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" />
              Quantités estimées par l&apos;IA — vérifiez-les avant d&apos;enregistrer.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="r-name">Nom</Label>
                <Input id="r-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="r-portions">Portions</Label>
                <Input
                  id="r-portions"
                  type="number"
                  min={1}
                  value={portions}
                  onChange={(e) => setPortions(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Ingrédients</Label>
              <div className="space-y-2">
                {rows.map((r, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      value={r.name}
                      onChange={(e) => updateRow(i, { name: e.target.value })}
                      placeholder="Ingrédient"
                      className="flex-1"
                    />
                    <Input
                      type="number"
                      value={r.qty ?? ""}
                      onChange={(e) =>
                        updateRow(i, { qty: e.target.value === "" ? null : Number(e.target.value) })
                      }
                      placeholder="Qté"
                      className="w-24"
                    />
                    <Input
                      value={r.unit ?? ""}
                      onChange={(e) => updateRow(i, { unit: e.target.value })}
                      placeholder="unité"
                      className="w-24"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeRow(i)}
                      aria-label="Supprimer"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button type="button" variant="outline" size="sm" onClick={addRow}>
                <Plus className="h-4 w-4" />
                <span className="ml-1">Ajouter un ingrédient</span>
              </Button>
            </div>

            <div className="space-y-2">
              <Label htmlFor="vi-steps">Étapes (une par ligne)</Label>
              <textarea
                id="vi-steps"
                value={stepsText}
                onChange={(e) => setStepsText(e.target.value)}
                rows={6}
                className="w-full rounded-md border border-input bg-background p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button onClick={onSave} disabled={save.isPending}>
                {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                <span className={save.isPending ? "ml-2" : ""}>Enregistrer la fiche</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {saved && (
        <Card className="mt-4 border-emerald-500/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              Fiche enregistrée
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex flex-wrap gap-4">
              <span>
                Coût matière :{" "}
                <strong>{formatCurrency(saved.cost.computed_cost_total ?? 0)}</strong>
              </span>
              <span>
                Coût / portion : <strong>{formatCurrency(saved.cost.cost_per_portion ?? 0)}</strong>
              </span>
              {saved.cost.food_cost_pct != null && (
                <span>
                  Food cost : <strong>{formatPercent(saved.cost.food_cost_pct)}</strong>
                </span>
              )}
            </div>
            {saved.cost.has_missing_prices && (
              <p className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                <AlertTriangle className="h-4 w-4" />
                Certains ingrédients n&apos;ont pas de prix — le coût est incomplet.
              </p>
            )}
            {saved.unmatched_ingredients.length > 0 && (
              <p className="text-muted-foreground">
                Produits à créer : {saved.unmatched_ingredients.join(", ")}
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <Button asChild variant="outline" size="sm">
                <Link href={`/recettes/${saved.recipe_id}`}>Ouvrir la fiche</Link>
              </Button>
              <Badge variant="secondary">{saved.name}</Badge>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
