import { api } from "@/lib/api";
import type {
  VideoExtractResult,
  VideoRecipeCandidate,
  VideoSaveResult,
  VideoSourceInfo,
} from "./types";

export async function extractVideo(url: string): Promise<VideoExtractResult> {
  const { data } = await api.post<VideoExtractResult>("/video/extract", { url });
  return data;
}

export async function extractVideoFile(file: File): Promise<VideoExtractResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<VideoExtractResult>("/video/extract-file", form, {
    headers: { "Content-Type": undefined as unknown as string },
  });
  return data;
}

export async function saveVideoRecipes(payload: {
  recipes: VideoRecipeCandidate[];
  source: VideoSourceInfo;
}): Promise<{ count: number; recipes: VideoSaveResult[] }> {
  const { data } = await api.post("/video/save", payload);
  return data;
}
