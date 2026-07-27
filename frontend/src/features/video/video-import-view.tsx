"use client";

import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import {
  Loader2,
  Wand2,
  CheckCircle2,
  Youtube,
  AlertTriangle,
  Upload,
  ListChecks,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { BackButton } from "@/components/back-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { useExtractVideo, useExtractVideoFile, useSaveVideoRecipes } from "@/hooks/use-video";
import type { VideoExtractResult, VideoRecipeCandidate, VideoSaveResponse, VideoSourceInfo } from "@/services/types";
import { CandidateCard, type CandidateState } from "./candidate-card";

const EMPTY_SOURCE: VideoSourceInfo = {
  platform: null,
  url: null,
  video_id: null,
  title: null,
  creator: null,
  thumbnail: null,
};

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

/** Trim/prune a candidate's editable-but-blank fields before it is sent to /video/save. */
function toPayload(c: CandidateState): VideoRecipeCandidate {
  return {
    name: c.name.trim(),
    description: c.description?.trim() || null,
    summary: c.summary?.trim() || null,
    yield_qty: c.yield_qty,
    ingredients: c.ingredients
      .filter((r) => r.name.trim())
      .map((r) => ({
        name: r.name.trim(),
        qty: r.qty === null || (r.qty as unknown) === "" ? null : Number(r.qty),
        unit: r.unit?.trim() || null,
      })),
    steps: c.steps.map((s) => s.trim()).filter(Boolean),
    prep_time_min: c.prep_time_min,
    cook_time_min: c.cook_time_min,
    tips: c.tips.map((s) => s.trim()).filter(Boolean),
    variants: c.variants.map((s) => s.trim()).filter(Boolean),
    allergens: c.allergens.map((s) => s.trim()).filter(Boolean),
    start_sec: c.start_sec,
    end_sec: c.end_sec,
  };
}

export function VideoImportView() {
  const [url, setUrl] = useState("");
  const [candidates, setCandidates] = useState<CandidateState[]>([]);
  const [source, setSource] = useState<VideoSourceInfo | null>(null);
  const [mergeFrom, setMergeFrom] = useState<number | null>(null);
  const [saved, setSaved] = useState<VideoSaveResponse | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const extract = useExtractVideo();
  const extractFile = useExtractVideoFile();
  const save = useSaveVideoRecipes();

  function loadResult(res: VideoExtractResult) {
    setSource(res.source);
    setCandidates(res.candidates.map((c) => ({ ...c, id: crypto.randomUUID(), selected: true })));
    setMergeFrom(null);
    toast.success(
      res.candidates.length > 1
        ? `${res.candidates.length} recettes détectées — vérifiez-les avant d'enregistrer.`
        : "Recette extraite — vérifiez les quantités estimées.",
    );
  }

  function onExtract(e: FormEvent) {
    e.preventDefault();
    const link = url.trim();
    if (!link || extract.isPending) return;
    setSaved(null);
    extract.mutate(link, {
      onSuccess: loadResult,
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
      onSuccess: loadResult,
      onError: (err) => toast.error(getApiErrorMessage(err)),
    });
  }

  function updateCandidate(i: number, next: CandidateState) {
    setCandidates((prev) => prev.map((c, idx) => (idx === i ? next : c)));
  }

  function toggleCandidate(i: number) {
    setCandidates((prev) =>
      prev.map((c, idx) => (idx === i ? { ...c, selected: !c.selected } : c)),
    );
  }

  function deleteCandidate(i: number) {
    setCandidates((prev) => prev.filter((_, idx) => idx !== i));
    setMergeFrom((prev) => {
      if (prev === null || prev === i) return null;
      return prev > i ? prev - 1 : prev;
    });
  }

  function mergeInto(target: number) {
    setCandidates((prev) => {
      if (mergeFrom === null || mergeFrom === target) return prev;
      const from = prev[mergeFrom];
      const into = prev[target];
      if (!from || !into) return prev;
      const merged: CandidateState = {
        ...into,
        ingredients: [...into.ingredients, ...from.ingredients],
        steps: [...into.steps, ...from.steps],
        start_sec:
          from.start_sec == null
            ? into.start_sec
            : into.start_sec == null
              ? from.start_sec
              : Math.min(into.start_sec, from.start_sec),
        end_sec:
          from.end_sec == null
            ? into.end_sec
            : into.end_sec == null
              ? from.end_sec
              : Math.max(into.end_sec, from.end_sec),
        tips: Array.from(new Set([...into.tips, ...from.tips])),
        variants: Array.from(new Set([...into.variants, ...from.variants])),
        allergens: Array.from(new Set([...into.allergens, ...from.allergens])),
      };
      return prev
        .map((c, idx) => (idx === target ? merged : c))
        .filter((_, idx) => idx !== mergeFrom);
    });
    setMergeFrom(null);
  }

  function onMergeClick(i: number) {
    if (candidates.length < 2) return;
    if (mergeFrom === null) {
      setMergeFrom(i);
      toast.message("Cliquez sur « Fusionner » d'une autre carte pour la fusionner avec celle-ci.");
      return;
    }
    if (mergeFrom === i) {
      setMergeFrom(null);
      return;
    }
    mergeInto(i);
  }

  function toggleSelectAll() {
    const allSelected = candidates.length > 0 && candidates.every((c) => c.selected);
    setCandidates((prev) => prev.map((c) => ({ ...c, selected: !allSelected })));
  }

  function onSave() {
    const selected = candidates.filter((c) => c.selected);
    if (selected.length === 0) {
      toast.error("Sélectionnez au moins une recette à enregistrer.");
      return;
    }
    const withNames = selected.every((c) => c.name.trim());
    if (!withNames) {
      toast.error("Donnez un nom à chaque recette sélectionnée.");
      return;
    }
    // Snapshot the ORDER of the ids being submitted: the backend saves recipe by
    // recipe and returns a partial success ({recipes, errors}), each result
    // carrying the `index` of the recipe it saved. We map that index back to the
    // card id captured here so we remove ONLY the cards that were actually
    // persisted — failed ones stay in the list for a retry, and a card the user
    // toggled mid-request is neither wrongly dropped (never sent) nor wrongly
    // kept (sent) because we key off what was submitted, not `.selected`.
    const submittedIds = selected.map((c) => c.id); // ordered = ordre d'envoi
    save.mutate(
      { recipes: selected.map(toPayload), source: source ?? EMPTY_SOURCE },
      {
        onSuccess: (res) => {
          setSaved(res);
          const savedIds = new Set(res.recipes.map((r) => submittedIds[r.index]));
          setCandidates((prev) => prev.filter((c) => !savedIds.has(c.id)));
          setMergeFrom(null);
          if (res.errors.length) {
            toast.error(
              `${res.errors.length} recette(s) non enregistrée(s) : ` +
                res.errors.map((e) => e.name).join(", "),
            );
          }
        },
        onError: (err) => toast.error(getApiErrorMessage(err)),
      },
    );
  }

  const selectedCount = candidates.filter((c) => c.selected).length;
  const allSelected = candidates.length > 0 && selectedCount === candidates.length;

  return (
    <>
      <BackButton />
      <PageHeader
        title="Import depuis une vidéo"
        description="Collez un lien (YouTube, TikTok, Instagram, Facebook…) OU importez un fichier vidéo. L'IA en extrait une ou plusieurs fiches recette modifiables, puis les chiffre avec vos prix."
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

      {candidates.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <ListChecks className="h-5 w-5" />
              Nous avons détecté {candidates.length} recette{candidates.length > 1 ? "s" : ""}
            </h2>
          </div>
          <p className="mt-1 flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4" />
            Quantités et découpage estimés par l&apos;IA — vérifiez avant d&apos;enregistrer.
          </p>

          {candidates.map((c, i) => (
            <CandidateCard
              key={c.id}
              value={c}
              index={i}
              videoId={source?.video_id ?? null}
              onChange={(next) => updateCandidate(i, next)}
              onDelete={() => deleteCandidate(i)}
              onToggle={() => toggleCandidate(i)}
              onMerge={() => onMergeClick(i)}
              mergeSource={mergeFrom === i}
            />
          ))}

          <div className="mt-4 flex flex-wrap items-center gap-3 border-t pt-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleSelectAll}
                className="h-4 w-4 rounded border-input accent-primary"
              />
              Tout (dé)sélectionner
            </label>
            <Button onClick={onSave} disabled={save.isPending || selectedCount === 0}>
              {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              <span className={save.isPending ? "ml-2" : ""}>
                Enregistrer les {selectedCount} sélectionnée{selectedCount > 1 ? "s" : ""}
              </span>
            </Button>
          </div>
        </div>
      )}

      {saved && (
        <Card className="mt-4 border-emerald-500/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              {saved.count} recette{saved.count > 1 ? "s" : ""} enregistrée{saved.count > 1 ? "s" : ""}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {saved.recipes.map((r) => (
              <div key={r.recipe_id} className="space-y-1 border-b pb-3 last:border-b-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">{r.name}</Badge>
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/recettes/${r.recipe_id}`}>Ouvrir la fiche</Link>
                  </Button>
                </div>
                <div className="flex flex-wrap gap-4 text-muted-foreground">
                  <span>
                    Coût matière :{" "}
                    <strong className="text-foreground">
                      {formatCurrency(r.cost.computed_cost_total ?? 0)}
                    </strong>
                  </span>
                  <span>
                    Coût / portion :{" "}
                    <strong className="text-foreground">
                      {formatCurrency(r.cost.cost_per_portion ?? 0)}
                    </strong>
                  </span>
                  {r.cost.food_cost_pct != null && (
                    <span>
                      Food cost :{" "}
                      <strong className="text-foreground">{formatPercent(r.cost.food_cost_pct)}</strong>
                    </span>
                  )}
                </div>
                {r.cost.has_missing_prices && (
                  <p className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="h-4 w-4" />
                    Certains ingrédients n&apos;ont pas de prix — le coût est incomplet.
                  </p>
                )}
                {r.unmatched_ingredients.length > 0 && (
                  <p className="text-muted-foreground">
                    Produits à créer : {r.unmatched_ingredients.join(", ")}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </>
  );
}
