import type { CostTrendPoint } from "@/services/types";

/** Keep only the most recent snapshot per recipe version. */
export function latestPerVersion(points: CostTrendPoint[]): CostTrendPoint[] {
  const map = new Map<string, CostTrendPoint>();
  for (const p of points) {
    const prev = map.get(p.recipe_version_id);
    if (
      !prev ||
      (p.computed_at && prev.computed_at && p.computed_at > prev.computed_at)
    ) {
      map.set(p.recipe_version_id, p);
    }
  }
  return [...map.values()];
}

export interface DailyCostPoint {
  date: string;
  avgCostPerPortion: number;
  avgFoodCost: number | null;
}

/** Average cost per portion / food cost across recipes, grouped by day. */
export function aggregateByDay(points: CostTrendPoint[]): DailyCostPoint[] {
  const groups = new Map<
    string,
    { costSum: number; costN: number; fcSum: number; fcN: number }
  >();
  for (const p of points) {
    if (!p.computed_at) continue;
    const date = p.computed_at.slice(0, 10);
    const g = groups.get(date) ?? { costSum: 0, costN: 0, fcSum: 0, fcN: 0 };
    if (p.cost_per_portion != null) {
      g.costSum += p.cost_per_portion;
      g.costN += 1;
    }
    if (p.food_cost_pct != null) {
      g.fcSum += p.food_cost_pct;
      g.fcN += 1;
    }
    groups.set(date, g);
  }
  return [...groups.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, g]) => ({
      date,
      avgCostPerPortion: g.costN ? g.costSum / g.costN : 0,
      avgFoodCost: g.fcN ? g.fcSum / g.fcN : null,
    }));
}

export function average(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((v): v is number => v != null);
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}
