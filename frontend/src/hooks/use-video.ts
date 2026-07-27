"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { extractVideo, extractVideoFile, saveVideoRecipes } from "@/services/video-service";
import type { VideoRecipeCandidate, VideoSourceInfo } from "@/services/types";

export function useExtractVideo() {
  return useMutation({ mutationFn: (url: string) => extractVideo(url) });
}

export function useExtractVideoFile() {
  return useMutation({ mutationFn: (file: File) => extractVideoFile(file) });
}

export function useSaveVideoRecipes() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { recipes: VideoRecipeCandidate[]; source: VideoSourceInfo }) =>
      saveVideoRecipes(payload),
    // Without this, the recipes were created server-side but did not appear on
    // /recettes until the cache went stale — the user thought the import failed
    // and imported it again. (The PDF-import flow already did this.)
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      // Partial success: `count` can be 0 when every recipe failed — the view's
      // onSuccess reports those errors, so don't also claim "0 recette
      // enregistrée" here. Only celebrate what was actually saved.
      if (res.count > 0) {
        toast.success(
          res.count > 1 ? `${res.count} recettes enregistrées.` : `${res.count} recette enregistrée.`,
        );
      }
    },
  });
}
