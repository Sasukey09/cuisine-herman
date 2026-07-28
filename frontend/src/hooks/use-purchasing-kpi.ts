"use client";

import { useQuery } from "@tanstack/react-query";

import { getPurchasingKpi } from "@/services/purchasing-kpi-service";

export function usePurchasingKpi() {
  return useQuery({ queryKey: ["purchasing", "kpi"], queryFn: getPurchasingKpi });
}
