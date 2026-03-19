import { type CaseStatus, type RecommendationStatus, type Severity } from "@/lib/types/case"

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
  if (!date || typeof date !== "string") return "—"
  const d = new Date(date)
  if (Number.isNaN(d.getTime())) return "—"
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d)
}

/** dd.mm.yyyy for eval run dates in subheaders */
export function formatDateDdMmYyyy(date: string) {
  const d = new Date(date)
  const day = String(d.getDate()).padStart(2, "0")
  const month = String(d.getMonth() + 1).padStart(2, "0")
  const year = d.getFullYear()
  return `${day}.${month}.${year}`
}

export function formatDateTime(date: string) {
  if (!date || typeof date !== "string") return "—"
  const d = new Date(date)
  if (Number.isNaN(d.getTime())) return "—"
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(d)
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

const caseStatusLabels: Record<CaseStatus, string> = {
  received: "Received",
  parsed: "Parsed",
  pending_review: "Pending Review",
  evaluated: "Evaluated",
  recommended: "Recommended",
  escalated: "Escalated",
  resolved: "Resolved",
}

export function displayCaseStatus(status: CaseStatus): string {
  return caseStatusLabels[status] ?? titleCase(status)
}

const recommendationStatusLabels: Record<RecommendationStatus, string> = {
  proceed: "Proceed",
  proceed_with_conditions: "Proceed with Conditions",
  cannot_proceed: "Cannot Proceed",
  not_evaluated: "Not Evaluated",
}

export function displayRecommendationStatus(status: RecommendationStatus): string {
  return recommendationStatusLabels[status] ?? titleCase(status)
}

const approvalTierLabels: Record<string, string> = {
  "AT-001": "Tier 1",
  "AT-002": "Tier 2",
  "AT-003": "Tier 3",
  "AT-004": "Tier 4",
}

export function displayApprovalTier(tier: string): string {
  const label = approvalTierLabels[tier]
  return label ? `${label} (${tier})` : tier
}

export function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

let regionDisplayNames: Intl.DisplayNames | null = null

function getRegionDisplayNames() {
  if (!regionDisplayNames) {
    regionDisplayNames = new Intl.DisplayNames(["en"], { type: "region" })
  }
  return regionDisplayNames
}

/** ISO 3166-1 alpha-2 (or common aliases) → English country/region name for UI labels. */
export function formatCountryDisplayName(code: string): string {
  const raw = code.trim()
  if (!raw) return "—"
  const upper = raw.toUpperCase()
  const normalized = upper === "UK" ? "GB" : upper
  if (normalized.length === 2) {
    try {
      const name = getRegionDisplayNames().of(normalized)
      if (name) return name
    } catch {
      // fall through
    }
  }
  return raw
}
