"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { DailyCostPoint } from "./utils";

const ACCENT = "#3b82f6"; // blue-500, readable in both themes

export function CostTrendChart({
  data,
  loading,
}: {
  data: DailyCostPoint[];
  loading?: boolean;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-base">Évolution du coût matière</CardTitle>
        <CardDescription>Coût moyen par portion dans le temps</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-[280px] w-full" />
        ) : data.length === 0 ? (
          <div className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">
            Pas encore de données de coût. Calculez le coût d&apos;une recette pour
            alimenter ce graphique.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={ACCENT} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={ACCENT} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                tickFormatter={(v) => formatDate(v)}
                fontSize={12}
                stroke="currentColor"
                className="text-muted-foreground"
              />
              <YAxis
                fontSize={12}
                stroke="currentColor"
                className="text-muted-foreground"
                tickFormatter={(v) => `${v}€`}
              />
              <Tooltip
                formatter={(value: number) => [formatCurrency(value), "Coût/portion"]}
                labelFormatter={(label) => formatDate(label as string)}
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Area
                type="monotone"
                dataKey="avgCostPerPortion"
                stroke={ACCENT}
                strokeWidth={2}
                fill="url(#costGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
