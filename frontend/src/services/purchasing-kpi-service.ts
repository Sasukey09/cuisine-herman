import { api } from "@/lib/api";
import type { PurchasingKpi } from "./types";

export async function getPurchasingKpi() {
  const { data } = await api.get<PurchasingKpi>("/purchasing/kpi");
  return data;
}
