"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getReportSources,
  listReports,
  createReport,
  deleteReport,
  runAdhocReport,
  runSavedReport,
} from "@/services/reports-service";

const KEY = ["reports"];

export function useReportSources() {
  return useQuery({ queryKey: [...KEY, "sources"], queryFn: getReportSources });
}

export function useReports() {
  return useQuery({ queryKey: KEY, queryFn: listReports });
}

export function useCreateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createReport,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteReport,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRunAdhocReport() {
  return useMutation({ mutationFn: runAdhocReport });
}

export function useRunSavedReport() {
  return useMutation({ mutationFn: runSavedReport });
}
