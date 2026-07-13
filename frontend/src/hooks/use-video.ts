"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { extractVideo, extractVideoFile, saveVideoRecipe } from "@/services/video-service";
import type { VideoIngredientDraft } from "@/services/types";

export function useExtractVideo() {
  return useMutation({ mutationFn: (url: string) => extractVideo(url) });
}

export function useExtractVideoFile() {
  return useMutation({ mutationFn: (file: File) => extractVideoFile(file) });
}

export function useSaveVideoRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: {
      name: string;
      yield_qty: number | null;
      ingredients: VideoIngredientDraft[];
      steps: string[];
    }) => saveVideoRecipe(payload),
    // Without this, the recipe was created server-side but did not appear on
    // /recettes until the cache went stale — the user thought the import failed
    // and imported it again. (The PDF-import flow already did this.)
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
  });
}
