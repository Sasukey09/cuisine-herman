"use client";

import { useMutation } from "@tanstack/react-query";

import { extractVideo, extractVideoFile, saveVideoRecipe } from "@/services/video-service";
import type { VideoIngredientDraft } from "@/services/types";

export function useExtractVideo() {
  return useMutation({ mutationFn: (url: string) => extractVideo(url) });
}

export function useExtractVideoFile() {
  return useMutation({ mutationFn: (file: File) => extractVideoFile(file) });
}

export function useSaveVideoRecipe() {
  return useMutation({
    mutationFn: (payload: {
      name: string;
      yield_qty: number | null;
      ingredients: VideoIngredientDraft[];
      steps: string[];
    }) => saveVideoRecipe(payload),
  });
}
