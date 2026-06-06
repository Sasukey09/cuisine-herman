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

export async function saveVideoRecipe(payload: {
  name: string;
  yield_qty: number | null;
  ingredients: VideoIngredientDraft[];
}): Promise<VideoSaveResult> {
  const { data } = await api.post<VideoSaveResult>("/video/save", payload);
  return data;
}
