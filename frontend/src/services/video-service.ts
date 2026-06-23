import { api } from "@/lib/api";
import type {
  VideoExtractResult,
  VideoIngredientDraft,
  VideoSaveResult,
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

export async function saveVideoRecipe(payload: {
  name: string;
  yield_qty: number | null;
  ingredients: VideoIngredientDraft[];
  steps: string[];
}): Promise<VideoSaveResult> {
  const { data } = await api.post<VideoSaveResult>("/video/save", payload);
  return data;
}
