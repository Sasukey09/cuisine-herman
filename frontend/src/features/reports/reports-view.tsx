"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, Save, Trash2, Plus, Download, FileSpreadsheet } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  useReportSources,
  useReports,
  useCreateReport,
  useDeleteReport,
  useRunAdhocReport,
  useRunSavedReport,
} from "@/hooks/use-reports";
import type { ReportFilter, ReportRunResult } from "@/services/types";

const OPS = [
  { value: "eq", label: "=" },
  { value: "ne", label: "≠" },
  { value: "contains", label: "contient" },
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" },
];

const selectClass =
  "h-9 rounded-md border border-input bg-card px-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function cell(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "boolean") return v ? "Oui" : "Non";
  return String(v);
}

function exportCsv(res: ReportRunResult, name: string) {
  const headers = res.columns.map((c) => c.label);
  const keys = res.columns.map((c) => c.key);
  const esc = (v: unknown) => {
    const s = cell(v).replace(/"/g, '""');
    return /[";\n]/.test(s) ? `"${s}"` : s;
  };
  const lines = [headers.join(";"), ...res.rows.map((r) => keys.map((k) => esc(r[k])).join(";"))];
  const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name || "rapport"}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ReportsView() {
  const sources = useReportSources();
  const saved = useReports();
  const create = useCreateReport();
  const remove = useDeleteReport();
  const runAdhoc = useRunAdhocReport();
  const runSaved = useRunSavedReport();

  const [source, setSource] = useState("");
  const [columns, setColumns] = useState<string[]>([]);
  const [filters, setFilters] = useState<ReportFilter[]>([]);
  const [sortField, setSortField] = useState("");
  const [sortDir, setSortDir] = useState("asc");
  const [limit, setLimit] = useState("");
  const [name, setName] = useState("");
  const [result, setResult] = useState<ReportRunResult | null>(null);

  const currentSource = useMemo(
    () => sources.data?.find((s) => s.key === source),
    [sources.data, source],
  );

  // initialise source when sources load
  useEffect(() => {
    if (!source && sources.data && sources.data.length > 0) {
      const first = sources.data[0];
      setSource(first.key);
      setColumns(first.columns.map((c) => c.key));
    }
  }, [sources.data, source]);

  function changeSource(key: string) {
    setSource(key);
    const s = sources.data?.find((x) => x.key === key);
    setColumns(s ? s.columns.map((c) => c.key) : []);
    setFilters([]);
    setSortField("");
    setResult(null);
  }

  function buildDefinition() {
    return {
      source,
      columns,
      filters: filters.filter((f) => f.field).map((f) => ({ field: f.field, op: f.op, value: f.value })),
      sort: sortField ? { field: sortField, dir: sortDir } : null,
      limit: limit ? Number(limit) : null,
    };
  }

  function onPreview() {
    if (!source || columns.length === 0) {
      toast.error("Choisissez une source et au moins une colonne.");
      return;
    }
    runAdhoc.mutate(buildDefinition(), {
      onSuccess: (res) => setResult(res),
      onError: (err) => toast.error(getApiErrorMessage(err)),
    });
  }

  function onSave() {
    if (!name.trim()) {
      toast.error("Donnez un nom au rapport.");
      return;
    }
    create.mutate(
      { name: name.trim(), definition: buildDefinition() },
      {
        onSuccess: () => {
          toast.success("Rapport enregistré.");
          setName("");
        },
        onError: (err) => toast.error(getApiErrorMessage(err)),
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Rapports personnalisés"
        description="Construisez des rapports sans développeur : source, colonnes, filtres — puis exportez en CSV."
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileSpreadsheet className="h-5 w-5" />
            Constructeur
          </CardTitle>
          <CardDescription>Choisissez une source de données et composez votre rapport.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label>Source</Label>
              <select value={source} onChange={(e) => changeSource(e.target.value)} className={cn(selectClass, "h-10")}>
                {(sources.data ?? []).map((s) => (
                  <option key={s.key} value={s.key}>{s.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Trier par</Label>
              <div className="flex gap-2">
                <select value={sortField} onChange={(e) => setSortField(e.target.value)} className={cn(selectClass, "h-10")}>
                  <option value="">—</option>
                  {(currentSource?.columns ?? []).map((c) => (
                    <option key={c.key} value={c.key}>{c.label}</option>
                  ))}
                </select>
                <select value={sortDir} onChange={(e) => setSortDir(e.target.value)} className={cn(selectClass, "h-10")}>
                  <option value="asc">croissant</option>
                  <option value="desc">décroissant</option>
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Limite</Label>
              <Input type="number" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="ex. 100" className="w-28" />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Colonnes</Label>
            <div className="flex flex-wrap gap-3">
              {(currentSource?.columns ?? []).map((c) => (
                <label key={c.key} className="flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={columns.includes(c.key)}
                    onChange={(e) =>
                      setColumns((prev) =>
                        e.target.checked ? [...prev, c.key] : prev.filter((k) => k !== c.key),
                      )
                    }
                  />
                  {c.label}
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Filtres</Label>
            <div className="space-y-2">
              {filters.map((f, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2">
                  <select
                    value={f.field}
                    onChange={(e) => setFilters((p) => p.map((x, idx) => (idx === i ? { ...x, field: e.target.value } : x)))}
                    className={selectClass}
                  >
                    <option value="">colonne…</option>
                    {(currentSource?.columns ?? []).map((c) => (
                      <option key={c.key} value={c.key}>{c.label}</option>
                    ))}
                  </select>
                  <select
                    value={f.op}
                    onChange={(e) => setFilters((p) => p.map((x, idx) => (idx === i ? { ...x, op: e.target.value } : x)))}
                    className={selectClass}
                  >
                    {OPS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  <Input
                    value={(f.value as string) ?? ""}
                    onChange={(e) => setFilters((p) => p.map((x, idx) => (idx === i ? { ...x, value: e.target.value } : x)))}
                    placeholder="valeur"
                    className="h-9 w-40"
                  />
                  <Button variant="ghost" size="icon" onClick={() => setFilters((p) => p.filter((_, idx) => idx !== i))} aria-label="Retirer">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFilters((p) => [...p, { field: "", op: "eq", value: "" }])}
            >
              <Plus className="h-4 w-4" />
              <span className="ml-1">Ajouter un filtre</span>
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button variant="gradient" onClick={onPreview} disabled={runAdhoc.isPending}>
              {runAdhoc.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              <span className="ml-1">Aperçu</span>
            </Button>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nom du rapport" className="w-56" />
            <Button variant="secondary" onClick={onSave} disabled={create.isPending}>
              <Save className="h-4 w-4" />
              <span className="ml-1">Enregistrer</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card className="mt-4">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Résultat · {result.count} ligne(s)</CardTitle>
            <Button variant="outline" size="sm" onClick={() => exportCsv(result, name)} disabled={result.rows.length === 0}>
              <Download className="h-4 w-4" />
              <span className="ml-1">Export CSV</span>
            </Button>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {result.columns.map((c) => (
                    <TableHead key={c.key}>{c.label}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.rows.map((row, i) => (
                  <TableRow key={i}>
                    {result.columns.map((c) => (
                      <TableCell key={c.key}>{cell(row[c.key])}</TableCell>
                    ))}
                  </TableRow>
                ))}
                {result.rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={result.columns.length} className="text-center text-muted-foreground">
                      Aucune ligne.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">Rapports enregistrés</CardTitle>
        </CardHeader>
        <CardContent>
          {saved.isError && (
            <ErrorState
              error={saved.error}
              onRetry={() => saved.refetch()}
              retrying={saved.isFetching}
            />
          )}
          {saved.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun rapport enregistré.</p>
          )}
          <div className="space-y-2">
            {(saved.data ?? []).map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3 border-b py-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{r.name}</span>
                  <Badge variant="secondary">{r.definition.source}</Badge>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      runSaved.mutate(r.id, {
                        onSuccess: (res) => {
                          setResult(res);
                          setName(r.name);
                        },
                        onError: (err) => toast.error(getApiErrorMessage(err)),
                      })
                    }
                  >
                    <Play className="h-4 w-4" />
                    <span className="ml-1">Exécuter</span>
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() =>
                      remove.mutate(r.id, {
                        onSuccess: () => toast.success("Rapport supprimé."),
                        onError: (err) => toast.error(getApiErrorMessage(err)),
                      })
                    }
                    aria-label="Supprimer"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </>
  );
}
