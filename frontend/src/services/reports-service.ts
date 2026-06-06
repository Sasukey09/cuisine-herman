import { api } from "@/lib/api";
import type {
  ReportSource,
  ReportDefinition,
  CustomReport,
  ReportRunResult,
} from "./types";

export async function getReportSources(): Promise<ReportSource[]> {
  const { data } = await api.get<ReportSource[]>("/reports/sources");
  return data;
}

export async function listReports(): Promise<CustomReport[]> {
  const { data } = await api.get<CustomReport[]>("/reports/");
  return data;
}

export async function createReport(payload: {
  name: string;
  definition: ReportDefinition;
}): Promise<CustomReport> {
  const { data } = await api.post<CustomReport>("/reports/", payload);
  return data;
}

export async function deleteReport(id: string): Promise<void> {
  await api.delete(`/reports/${id}`);
}

export async function runAdhocReport(definition: ReportDefinition): Promise<ReportRunResult> {
  const { data } = await api.post<ReportRunResult>("/reports/run", definition);
  return data;
}

export async function runSavedReport(id: string): Promise<ReportRunResult> {
  const { data } = await api.get<ReportRunResult>(`/reports/${id}/run`);
  return data;
}
