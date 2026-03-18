import { type Severity } from "@/lib/types/case"

export function formatCurrency(
  value: number | null | undefined,
  currency = "EUR"
) {
  if (value === null || value === undefined) {
    return "Not provided"
  }

  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(date))
}

export function formatDateTime(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date))
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat("en-GB").format(value)
}

export function formatPercentage(value: number) {
  return `${Math.round(value)}%`
}

export function severityTone(severity: Severity) {
  switch (severity) {
    case "critical":
      return "destructive"
    case "high":
      return "warning"
    case "medium":
      return "amber"
    default:
      return "neutral"
  }
}

export function scoreTone(score: number, inverse = false) {
  const normalized = inverse ? 100 - score : score
  if (normalized >= 80) {
    return "text-emerald-700"
  }
  if (normalized >= 60) {
    return "text-amber-700"
  }
  return "text-rose-700"
}
