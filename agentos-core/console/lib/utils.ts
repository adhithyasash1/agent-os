import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number | null | undefined) {
  if (typeof score !== "number" || Number.isNaN(score)) return "0.00";
  return score.toFixed(2);
}

export function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "0%";
  return `${Math.round(value * 100)}%`;
}

export function formatWhen(value: string | null | undefined) {
  if (!value) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

export function scoreTone(score: number | null | undefined) {
  if (typeof score !== "number") return "text-muted";
  if (score >= 0.6) return "text-success";
  if (score >= 0.35) return "text-gold";
  return "text-danger";
}
