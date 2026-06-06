import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value?: number | null, currency = "EUR") {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency }).format(value);
}

export function formatNumber(value?: number | null, digits = 2) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits }).format(value);
}

export function formatDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(d);
}

export function formatPercent(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(value)} %`;
}
