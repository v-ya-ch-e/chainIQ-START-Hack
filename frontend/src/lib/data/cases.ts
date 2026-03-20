import { chainIqApi } from "@/lib/api/client"
import type { PipelineResultOut } from "@/lib/api/types"
import type {
  AuditFeedEvent,
  AuditFeedMeta,
  AuditPageData,
  AuditSummaryMetric,
  CaseIntakeInput,
  CaseDraftPayload,
  CaseDetail,
  CaseListItem,
  CaseStatus,
  CategoryOption,
  CreateCasePayload,
  DashboardInsights,
  DashboardMetric,
  DashboardPageData,
  ExtractionResult,
  EvaluationRunDetail,
  QueueEscalationItem,
  RecommendationStatus,
  RuleCheckResult,
  ScenarioTag,
  Severity,
  SupplierRow,
} from "@/lib/types/case"

type RequestRow = {
  request_id: string
  created_at: string
  request_channel: string
  request_language: string
  business_unit: string
  country: string
  site: string
  requester_id: string
  requester_role: string | null
  submitted_for_id: string
  category_id: number
  title: string
  request_text: string
  currency: string
  budget_amount: string | number | null
  quantity: string | number | null
  unit_of_measure: string
  required_by_date: string
  preferred_supplier_mentioned: string | null
  incumbent_supplier: string | null
  contract_type_requested: string
  data_residency_constraint: boolean
  esg_requirement: boolean
  status: string
  scenario_tags?: string[]
}

type RequestDetail = RequestRow & {
  delivery_countries: Array<{ id: number; country_code: string }>
  scenario_tags: Array<{ id: number; tag: string }>
  category_l1: string | null
  category_l2: string | null
}

type HistoricalAward = {
  award_id: string
  request_id: string
  award_date: string
  category_id: number
  country: string
  business_unit: string
  supplier_id: string
  supplier_name: string
  total_value: string | number
  currency: string
  quantity: string | number
  required_by_date: string
  awarded: boolean
  award_rank: number
  decision_rationale: string
  policy_compliant: boolean
  preferred_supplier_used: boolean
  escalation_required: boolean
  escalated_to: string | null
  savings_pct: string | number
  lead_time_days: number
  risk_score_at_award: number
  notes: string | null
}

type CategoryRow = {
  id: number
  category_l1: string
  category_l2: string
  category_description: string
  typical_unit: string
  pricing_model: string
}

type RequestOverview = {
  request: {
    request_id: string
    title: string
    category_l1: string | null
    category_l2: string | null
    currency: string
    budget_amount: string | null
    quantity: string | null
    country: string
    delivery_countries: string[]
    scenario_tags: string[]
    required_by_date: string
    data_residency_constraint: boolean
    esg_requirement: boolean
    preferred_supplier_mentioned: string | null
    incumbent_supplier: string | null
    status: string
  }
  compliant_suppliers: Array<{
    supplier_id: string
    supplier_name: string
    country_hq: string
    currency: string
    quality_score: number
    risk_score: number
    esg_score: number
    preferred_supplier: boolean
    data_residency_supported: boolean
  }>
  pricing: Array<{
    pricing_id: string
    supplier_id: string
    supplier_name: string
    region: string
    currency: string
    min_quantity: number
    max_quantity: number
    unit_price: string | number
    expedited_unit_price: string | number
    total_price: string | number
    expedited_total_price: string | number
    standard_lead_time_days: number
    expedited_lead_time_days: number
    moq: number
  }>
  applicable_rules: {
    category_rules: Array<Record<string, unknown>>
    geography_rules: Array<Record<string, unknown>>
  }
  approval_tier: {
    threshold_id: string
    currency: string
    min_amount: string
    max_amount: string | null
    min_supplier_quotes: number
    policy_note: string | null
    managers: string[]
    deviation_approvers: string[]
  } | null
  historical_awards: Array<Record<string, unknown>>
}

type AuditListOut = {
  items: Array<{
    id: number
    request_id: string
    run_id: string | null
    timestamp: string
    level: string
    category: string
    step_name: string | null
    message: string
    details: Record<string, unknown> | null
    source: string
  }>
  total: number
}

type AuditSummaryOut = {
  request_id: string
  total_entries: number
  by_level: Array<{ level: string; count: number }>
  by_category: Array<{ category: string; count: number }>
  distinct_policies: string[]
  distinct_suppliers: string[]
  escalation_count: number
  first_event?: string | null
  last_event?: string | null
}

type AuditFetchResult = {
  audit: AuditListOut
  meta: AuditFeedMeta
}

type EscalationQueueApiRow = {
  escalation_id: string
  request_id: string
  title: string
  category: string
  business_unit: string
  country: string
  rule_id: string
  rule_label: string
  trigger: string
  escalate_to: string
  blocking: boolean
  status: "open" | "resolved"
  created_at: string
  last_updated: string
  recommendation_status: RecommendationStatus
}

type EvaluationCheckApi = {
  check_id: string
  rule_id: string
  version_id: string
  supplier_id: string | null
  result: string | null
  checked_at: string
  skipped?: boolean | null
  skip_reason?: string | null
  evidence?: Record<string, unknown> | null
  rule_name?: string | null
  /** Some proxies/clients may emit camelCase */
  ruleName?: string | null
  version_snapshot?: Record<string, unknown> | null
  dynamic_snapshot?: Record<string, unknown> | null
  dynamic_rule_version?: number | null
  dynamicRuleVersion?: number | null
}

type SupplierBreakdownApi = {
  supplier_id: string
  supplier_name: string | null
  hard_rule_checks: EvaluationCheckApi[]
  policy_checks: EvaluationCheckApi[]
  excluded: boolean
  exclusion_rule_id: string | null
  exclusion_reason: string | null
}

type EvaluationDetailApi = {
  run_id: string
  request_id: string
  status: string
  started_at: string
  finished_at: string | null
  supplier_shortlist?: Array<Record<string, unknown>>
  suppliers_excluded?: Array<{ supplier_id: string; supplier_name: string; reason: string }>
  supplier_breakdowns: SupplierBreakdownApi[]
}

type DashboardRawData = {
  requests: RequestRow[]
  awards: HistoricalAward[]
  categoriesMap: Map<number, string>
  escalationRows: QueueEscalationItem[]
}

type SpendByCategoryRow = {
  category_l1?: string | null
  category_l2?: string | null
  total_spend?: string | number | null
  award_count?: string | number | null
}

type DashboardAnalyticsData = {
  spendByCategory: SpendByCategoryRow[]
  spendBySupplier: Array<{
    supplier_name?: string
    total_spend?: string
  }>
  supplierWinRates: Array<{ win_rate?: string }>
}

type DashboardSnapshot = {
  metrics: DashboardMetric[]
  cases: CaseListItem[]
  insights: DashboardInsights
  asOf: string
  cachedAtMs: number
}

const DASHBOARD_CACHE_TTL_MS = 15_000
const AUDIT_PAGE_SIZE = 500

const STATUS_MAP: Record<string, CaseStatus> = {
  new: "received",
  submitted: "parsed",
  in_review: "pending_review",
  error: "pending_review",
  invalid: "pending_review",
  pending_review: "pending_review",
  evaluated: "evaluated",
  recommended: "recommended",
  escalated: "escalated",
  resolved: "resolved",
  received: "received",
  parsed: "parsed",
}

let dashboardSnapshot: DashboardSnapshot | null = null
let dashboardSnapshotPromise: Promise<DashboardSnapshot> | null = null

const statusLabels: Record<CaseStatus, string> = {
  received: "Received",
  parsed: "Parsed",
  pending_review: "Pending review",
  evaluated: "Evaluated",
  recommended: "Recommended",
  escalated: "Escalated",
  resolved: "Resolved",
}

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeStatus(status: string): CaseStatus {
  return STATUS_MAP[status] ?? "received"
}

function normalizeTags(tags: string[]): ScenarioTag[] {
  return tags.filter(Boolean)
}

function recommendationStatusFrom(
  hasBlocking: boolean,
  hasEscalation: boolean,
  status: CaseStatus,
): RecommendationStatus {
  if (status === "received" || status === "parsed") return "not_evaluated"
  if (hasBlocking) return "cannot_proceed"
  if (hasEscalation || status === "pending_review" || status === "escalated") {
    return "proceed_with_conditions"
  }
  return "proceed"
}

function mapEscalationQueueRow(row: EscalationQueueApiRow): QueueEscalationItem {
  return {
    escalationId: row.escalation_id,
    caseId: row.request_id,
    title: row.title,
    category: row.category,
    businessUnit: row.business_unit,
    country: row.country,
    ruleId: row.rule_id,
    ruleLabel: row.rule_label,
    trigger: row.trigger,
    escalateTo: row.escalate_to,
    blocking: row.blocking,
    status: row.status,
    createdAt: row.created_at,
    lastUpdated: row.last_updated,
    recommendationStatus: row.recommendation_status,
  }
}

function isNotFoundError(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  return (
    error.message.includes("404") ||
    error.message.includes("Not Found") ||
    error.message.includes("not found")
  )
}

function fallbackReasonFromError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return "Unable to refresh dashboard data from backend."
}

function parseAuditKind(category: string): AuditFeedEvent["kind"] {
  if (category === "escalation") return "escalation"
  if (category === "policy") return "policy"
  if (category === "supplier_filter" || category === "compliance") return "supplier"
  if (category === "validation" || category === "recommendation") return "interpretation"
  if (category === "data_access") return "source"
  return "audit"
}

function severityFrom(value: unknown): Severity {
  if (value === "critical" || value === "high" || value === "medium") {
    return value
  }
  return "low"
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function emptyAuditList(): AuditListOut {
  return {
    items: [],
    total: 0,
  }
}

function emptyAuditSummary(requestId: string): AuditSummaryOut {
  return {
    request_id: requestId,
    total_entries: 0,
    by_level: [],
    by_category: [],
    distinct_policies: [],
    distinct_suppliers: [],
    escalation_count: 0,
    first_event: null,
    last_event: null,
  }
}

async function fetchCaseAuditLogs(requestId: string): Promise<AuditListOut> {
  try {
    return (await chainIqApi.orgLogs.audit.byRequest(requestId, {
      limit: 500,
    })) as AuditListOut
  } catch {
    try {
      return (await chainIqApi.pipeline.audit(requestId, {
        limit: 500,
      })) as AuditListOut
    } catch {
      return emptyAuditList()
    }
  }
}

async function fetchCaseAuditSummary(requestId: string): Promise<AuditSummaryOut> {
  try {
    return (await chainIqApi.orgLogs.audit.summary(requestId)) as AuditSummaryOut
  } catch {
    try {
      return (await chainIqApi.pipeline.auditSummary(requestId)) as AuditSummaryOut
    } catch {
      return emptyAuditSummary(requestId)
    }
  }
}

async function getAllRequests(): Promise<RequestRow[]> {
  const limit = 200
  let skip = 0
  const items: RequestRow[] = []

  while (true) {
    const page = (await chainIqApi.requests.list({
      skip,
      limit,
    })) as { items: RequestRow[]; total: number; limit: number }
    items.push(...page.items)
    skip += page.limit
    if (skip >= page.total) break
  }

  return items
}

async function getAllAwards(): Promise<HistoricalAward[]> {
  const limit = 200
  let skip = 0
  const items: HistoricalAward[] = []

  while (true) {
    const page = (await chainIqApi.awards.list({
      skip,
      limit,
    })) as { items: HistoricalAward[]; total: number; limit: number }
    items.push(...page.items)
    skip += page.limit
    if (skip >= page.total) break
  }

  return items
}

async function getCategoriesMap() {
  const categories = (await chainIqApi.categories.list()) as CategoryRow[]
  return new Map<number, string>(
    categories.map((category) => [
      category.id,
      `${category.category_l1} / ${category.category_l2}`,
    ]),
  )
}

async function fetchEscalationQueueRows(): Promise<QueueEscalationItem[]> {
  const rows = (await chainIqApi.escalations.queue()) as EscalationQueueApiRow[]
  return rows.map(mapEscalationQueueRow)
}

async function fetchEscalationRowsByRequest(
  requestId: string,
): Promise<QueueEscalationItem[]> {
  const rows = (await chainIqApi.escalations.byRequest(
    requestId,
  )) as EscalationQueueApiRow[]
  return rows.map(mapEscalationQueueRow)
}

async function fetchEvaluationRunsByRequest(
  requestId: string,
): Promise<EvaluationDetailApi[]> {
  const urls = getApiUrlCandidates(
    `/api/rule-versions/evaluations/by-request/${encodeURIComponent(requestId)}`,
  )
  for (const url of urls) {
    try {
      const response = await fetch(url, { cache: "no-store" })
      if (!response.ok) continue
      const payload = (await response.json()) as unknown
      return Array.isArray(payload) ? (payload as EvaluationDetailApi[]) : []
    } catch {
      // Try next candidate.
    }
  }
  return []
}

async function fetchEvaluationRunById(runId: string): Promise<EvaluationDetailApi | null> {
  const urls = getApiUrlCandidates(
    `/api/rule-versions/evaluations/${encodeURIComponent(runId)}`,
  )
  let sawNotFound = false
  let lastError: unknown = null

  for (const url of urls) {
    try {
      const response = await fetch(url, { cache: "no-store" })
      if (response.status === 404) {
        sawNotFound = true
        continue
      }
      if (!response.ok) {
        lastError = new Error(
          `Request failed (${response.status}) for /api/rule-versions/evaluations/${runId}`,
        )
        continue
      }
      return (await response.json()) as EvaluationDetailApi
    } catch (error) {
      lastError = error
    }
  }

  if (sawNotFound) return null
  if (lastError instanceof Error) throw lastError
  return null
}

function extractPrice(entry: Record<string, unknown>, prefix: string): number {
  for (const key of Object.keys(entry)) {
    if (key.startsWith(prefix) && typeof entry[key] === "number") {
      return entry[key] as number
    }
  }
  return 0
}

function mapSupplierShortlistEntry(
  entry: Record<string, unknown>,
  index: number,
): SupplierRow {
  const totalPrice =
    extractPrice(entry, "total_price_") || extractPrice(entry, "total_price") || 0
  const unitPrice =
    extractPrice(entry, "unit_price_") || extractPrice(entry, "unit_price") || 0
  const expeditedTotal =
    extractPrice(entry, "expedited_total_") ||
    extractPrice(entry, "expedited_total") ||
    0
  const expeditedUnitPrice =
    extractPrice(entry, "expedited_unit_price_") ||
    extractPrice(entry, "expedited_unit_price") ||
    0

  return {
    rank: (entry.rank as number) ?? index + 1,
    supplierId: (entry.supplier_id as string) ?? "",
    supplierName: (entry.supplier_name as string) ?? "",
    countryHq:
      typeof entry.country_hq === "string" ? (entry.country_hq as string) : undefined,
    currency:
      typeof entry.currency === "string" ? (entry.currency as string) : undefined,
    preferred: (entry.preferred as boolean) ?? false,
    incumbent: (entry.incumbent as boolean) ?? false,
    pricingTierApplied: (entry.pricing_tier_applied as string) ?? "",
    region: typeof entry.region === "string" ? (entry.region as string) : undefined,
    minQuantity:
      typeof entry.min_quantity === "number" ? (entry.min_quantity as number) : undefined,
    maxQuantity:
      typeof entry.max_quantity === "number" ? (entry.max_quantity as number) : undefined,
    moq: typeof entry.moq === "number" ? (entry.moq as number) : undefined,
    unitPrice,
    totalPrice,
    standardLeadTimeDays: (entry.standard_lead_time_days as number) ?? 0,
    expeditedLeadTimeDays: (entry.expedited_lead_time_days as number) ?? 0,
    expeditedUnitPrice,
    expeditedTotal,
    qualityScore: (entry.quality_score as number) ?? 0,
    riskScore: (entry.risk_score as number) ?? 0,
    esgScore: (entry.esg_score as number) ?? 0,
    policyCompliant: (entry.policy_compliant as boolean) ?? true,
    coversDeliveryCountry: (entry.covers_delivery_country as boolean) ?? true,
    dataResidencySupported:
      typeof entry.data_residency_supported === "boolean"
        ? (entry.data_residency_supported as boolean)
        : undefined,
    recommendationNote:
      (entry.recommendation_note as string) ??
      "Eligible supplier after policy and region checks.",
  }
}

function pickRuleNameFromEvaluationCheck(check: EvaluationCheckApi): string | null {
  const a = check.rule_name
  const b = check.ruleName
  if (typeof a === "string" && a.trim()) return a.trim()
  if (typeof b === "string" && b.trim()) return b.trim()
  return null
}

/** API may return JSON columns as objects or (rarely) JSON strings. */
function coerceJsonObjectRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as unknown
      if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      /* ignore */
    }
  }
  return null
}

function coerceDynamicRuleVersion(check: EvaluationCheckApi): number | null {
  const raw = check as Record<string, unknown>
  const v = raw.dynamic_rule_version ?? raw.dynamicRuleVersion
  if (typeof v === "number" && Number.isFinite(v)) return v
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) {
    return Number(v)
  }
  return null
}

function mapEvaluationRunDetail(raw: EvaluationDetailApi): EvaluationRunDetail {
  const normalizeCheckResult = (value: string | null | undefined): RuleCheckResult => {
    if (
      value === "passed" ||
      value === "failed" ||
      value === "warned" ||
      value === "skipped"
    ) {
      return value
    }
    return "skipped"
  }

  const supplierShortlist = (raw.supplier_shortlist ?? []).map((entry, i) =>
    mapSupplierShortlistEntry(entry as Record<string, unknown>, i),
  )
  const excludedSuppliersFromRun = (raw.suppliers_excluded ?? []).map((entry) => ({
    supplierId: entry.supplier_id,
    supplierName: entry.supplier_name,
    reason: entry.reason,
    hardExclusion: (entry.reason ?? "").toLowerCase().includes("restricted"),
  }))

  return {
    runId: raw.run_id,
    requestId: raw.request_id,
    status: raw.status,
    startedAt: raw.started_at,
    finishedAt: raw.finished_at,
    supplierBreakdowns: raw.supplier_breakdowns.map((entry) => ({
      supplierId: entry.supplier_id,
      supplierName: entry.supplier_name,
      excluded: entry.excluded,
      exclusionRuleId: entry.exclusion_rule_id,
      exclusionReason: entry.exclusion_reason,
      hardRuleChecks: entry.hard_rule_checks.map((check) => ({
        checkId: check.check_id,
        ruleId: check.rule_id,
        versionId: check.version_id,
        supplierId: check.supplier_id,
        result: check.skipped ? "skipped" : normalizeCheckResult(check.result),
        checkedAt: check.checked_at,
        skipped: check.skipped ?? null,
        skipReason: check.skip_reason ?? null,
        evidence: check.evidence ?? null,
        ruleName: pickRuleNameFromEvaluationCheck(check),
        versionSnapshot:
          coerceJsonObjectRecord(check.version_snapshot) ??
          coerceJsonObjectRecord((check as Record<string, unknown>).versionSnapshot),
        dynamicSnapshot:
          coerceJsonObjectRecord(check.dynamic_snapshot) ??
          coerceJsonObjectRecord((check as Record<string, unknown>).dynamicSnapshot),
        dynamicRuleVersion: coerceDynamicRuleVersion(check),
      })),
      policyChecks: entry.policy_checks.map((check) => ({
        checkId: check.check_id,
        ruleId: check.rule_id,
        versionId: check.version_id,
        supplierId: check.supplier_id,
        result: normalizeCheckResult(check.result),
        checkedAt: check.checked_at,
        skipped: check.skipped ?? null,
        skipReason: check.skip_reason ?? null,
        evidence: check.evidence ?? null,
        ruleName: pickRuleNameFromEvaluationCheck(check),
        versionSnapshot:
          coerceJsonObjectRecord(check.version_snapshot) ??
          coerceJsonObjectRecord((check as Record<string, unknown>).versionSnapshot),
        dynamicSnapshot:
          coerceJsonObjectRecord(check.dynamic_snapshot) ??
          coerceJsonObjectRecord((check as Record<string, unknown>).dynamicSnapshot),
        dynamicRuleVersion: coerceDynamicRuleVersion(check),
      })),
    })),
    supplierShortlist: supplierShortlist.length > 0 ? supplierShortlist : undefined,
    excludedSuppliersFromRun:
      excludedSuppliersFromRun.length > 0 ? excludedSuppliersFromRun : undefined,
  }
}

async function fetchDashboardRawData(): Promise<DashboardRawData> {
  const [requests, awards, categoriesMap, escalationRows] = await Promise.all([
    getAllRequests(),
    getAllAwards(),
    getCategoriesMap(),
    fetchEscalationQueueRows(),
  ])

  return {
    requests,
    awards,
    categoriesMap,
    escalationRows,
  }
}

async function fetchDashboardAnalyticsData(): Promise<DashboardAnalyticsData> {
  const [spendByCategory, spendBySupplier, supplierWinRates] = await Promise.all([
    chainIqApi.analytics.spendByCategory().catch(() => []),
    chainIqApi.analytics.spendBySupplier().catch(() => []),
    chainIqApi.analytics.supplierWinRates().catch(() => []),
  ])

  return {
    spendByCategory: spendByCategory as SpendByCategoryRow[],
    spendBySupplier: spendBySupplier as DashboardAnalyticsData["spendBySupplier"],
    supplierWinRates: supplierWinRates as DashboardAnalyticsData["supplierWinRates"],
  }
}

async function buildDashboardMetricsFromData({
  requests,
  awards,
  escalationRows,
}: Pick<DashboardRawData, "requests" | "awards" | "escalationRows">, analytics?: DashboardAnalyticsData): Promise<DashboardMetric[]> {
  const resolvedAnalytics = analytics ?? (await fetchDashboardAnalyticsData())
  const { spendByCategory, spendBySupplier, supplierWinRates } = resolvedAnalytics

  const blockingCases = new Set(
    escalationRows
      .filter((entry) => entry.blocking && entry.status !== "resolved")
      .map((entry) => entry.caseId),
  )

  const totalSpend = spendByCategory
    .map((row) => toNumber(row.total_spend ?? null) ?? 0)
    .reduce((acc, value) => acc + value, 0)

  const topSupplier = spendBySupplier[0]
  const topWinRate = supplierWinRates[0]

  return [
    {
      label: "Total Cases",
      value: requests.length,
      helper: "All sourcing requests available in the database",
      tone: "default",
    },
    {
      label: "Pending Review",
      value: requests.filter(
        (entry) =>
          normalizeStatus(entry.status) === "pending_review" ||
          normalizeStatus(entry.status) === "escalated",
      ).length,
      helper: "Requests requiring review or additional action",
      tone: "warning",
    },
    {
      label: "Blocking Cases",
      value: blockingCases.size,
      helper: "Requests with policy blockers requiring escalation",
      tone: "destructive",
    },
    {
      label: "Awarded Outcomes",
      value: awards.filter((entry) => entry.awarded).length,
      helper: "Historical decisions with a selected supplier",
      tone: "success",
    },
    {
      label: "Awarded Spend",
      value: totalSpend,
      valueLabel: `EUR ${new Intl.NumberFormat("en-GB", {
        maximumFractionDigits: 0,
      }).format(totalSpend)}`,
      helper: "Aggregated winner spend across categories",
      tone: "info",
    },
    {
      label: "Top Supplier",
      value: toNumber(topWinRate?.win_rate ?? null) ?? 0,
      valueLabel: topSupplier?.supplier_name
        ? `${topSupplier.supplier_name}`
        : "—",
      helper: topWinRate?.win_rate
        ? `Win rate ${Number(topWinRate.win_rate).toFixed(1)}%`
        : "—",
      tone: "info",
    },
  ]
}

function buildCaseListFromData({
  requests,
  awards,
  categoriesMap,
  escalationRows,
}: DashboardRawData): CaseListItem[] {
  const awardsByRequest = new Map<string, HistoricalAward[]>()
  for (const award of awards) {
    const bucket = awardsByRequest.get(award.request_id) ?? []
    bucket.push(award)
    awardsByRequest.set(award.request_id, bucket)
  }

  const escalationsByRequest = new Map<string, QueueEscalationItem[]>()
  for (const escalation of escalationRows) {
    const bucket = escalationsByRequest.get(escalation.caseId) ?? []
    bucket.push(escalation)
    escalationsByRequest.set(escalation.caseId, bucket)
  }

  return requests.map((request) => {
    const requestAwards = awardsByRequest.get(request.request_id) ?? []
    const requestEscalations = escalationsByRequest.get(request.request_id) ?? []
    const normalizedTags = normalizeTags(request.scenario_tags ?? [])
    const hasBlockingEscalation = requestEscalations.some(
      (entry) => entry.blocking && entry.status !== "resolved",
    )
    const hasEscalation = requestEscalations.some(
      (entry) => entry.status !== "resolved",
    )
    const status = normalizeStatus(request.status)
    const recommendationStatus = recommendationStatusFrom(
      hasBlockingEscalation,
      hasEscalation,
      status,
    )
    const winner = requestAwards.find(
      (entry) => entry.awarded && entry.award_rank === 1,
    )
    const fallbackSupplier = requestAwards.find((entry) => entry.award_rank === 1)
    const lastEscalationUpdate = requestEscalations
      .map((entry) => new Date(entry.lastUpdated).getTime())
      .sort((a, b) => b - a)[0]

    return {
      requestId: request.request_id,
      title: request.title,
      category: categoriesMap.get(request.category_id) ?? "",
      businessUnit: request.business_unit,
      countryLabel: request.country,
      budgetAmount: toNumber(request.budget_amount),
      currency: request.currency,
      requiredByDate: request.required_by_date,
      status,
      scenarioTags: normalizedTags,
      recommendationStatus,
      escalationStatus: hasBlockingEscalation
        ? "blocking"
        : hasEscalation
          ? "advisory"
          : "none",
      lastUpdated: new Date(
        Math.max(
          new Date(request.created_at).getTime(),
          lastEscalationUpdate ?? 0,
        ),
      ).toISOString(),
      supplierLabel:
        winner?.supplier_name ??
        fallbackSupplier?.supplier_name ??
        request.incumbent_supplier ??
        "",
      needsAttention:
        hasBlockingEscalation ||
        status === "pending_review" ||
        status === "escalated" ||
        (recommendationStatus !== "proceed" && recommendationStatus !== "not_evaluated"),
    }
  })
}

function buildDashboardInsights({
  cases,
  analytics,
}: {
  cases: CaseListItem[]
  analytics: DashboardAnalyticsData
}): DashboardInsights {
  const statusCounts = new Map<CaseStatus, number>()
  const categorySet = new Set<string>()
  const countrySet = new Set<string>()

  for (const entry of cases) {
    statusCounts.set(entry.status, (statusCounts.get(entry.status) ?? 0) + 1)
    categorySet.add(entry.category)
    countrySet.add(entry.countryLabel)
  }

  const statusBreakdown = (Object.keys(statusLabels) as CaseStatus[])
    .map((status) => ({
      status,
      label: statusLabels[status],
      count: statusCounts.get(status) ?? 0,
    }))
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.count - a.count)

  const spendByCategory = analytics.spendByCategory
    .map((entry) => {
      const categoryL1 = entry.category_l1?.trim() ?? ""
      const categoryL2 = entry.category_l2?.trim() ?? ""
      const category = categoryL2
        ? `${categoryL1} / ${categoryL2}`
        : categoryL1 || "Unknown category"

      return {
        category,
        totalSpend: toNumber(entry.total_spend ?? null) ?? 0,
        awardCount: toNumber(entry.award_count ?? null) ?? 0,
      }
    })
    .sort((a, b) => b.totalSpend - a.totalSpend)
    .slice(0, 8)

  return {
    statusBreakdown,
    spendByCategory,
    filterOptions: {
      statuses: (Object.keys(statusLabels) as CaseStatus[]).filter(
        (status) => (statusCounts.get(status) ?? 0) > 0,
      ),
      categories: Array.from(categorySet).sort((a, b) => a.localeCompare(b)),
      countries: Array.from(countrySet).sort((a, b) => a.localeCompare(b)),
    },
  }
}

function isDashboardSnapshotFresh(
  snapshot: DashboardSnapshot,
  nowMs: number,
): boolean {
  return nowMs - snapshot.cachedAtMs < DASHBOARD_CACHE_TTL_MS
}

function toDashboardPageData(
  snapshot: DashboardSnapshot,
  mode: "fresh" | "stale",
  reason?: string,
): DashboardPageData {
  return {
    metrics: snapshot.metrics,
    cases: snapshot.cases,
    insights: snapshot.insights,
    dataState: {
      mode,
      asOf: snapshot.asOf,
      ...(reason ? { reason } : {}),
    },
  }
}

async function refreshDashboardSnapshot(): Promise<DashboardSnapshot> {
  const rawData = await fetchDashboardRawData()
  const analytics = await fetchDashboardAnalyticsData()
  const metrics = await buildDashboardMetricsFromData(rawData, analytics)
  const cases = buildCaseListFromData(rawData)
  const snapshot: DashboardSnapshot = {
    metrics,
    cases,
    insights: buildDashboardInsights({
      cases,
      analytics,
    }),
    asOf: new Date().toISOString(),
    cachedAtMs: Date.now(),
  }
  dashboardSnapshot = snapshot

  return snapshot
}

async function loadDashboardSnapshotWithDeduping(): Promise<DashboardSnapshot> {
  if (!dashboardSnapshotPromise) {
    dashboardSnapshotPromise = refreshDashboardSnapshot().finally(() => {
      dashboardSnapshotPromise = null
    })
  }

  return await dashboardSnapshotPromise
}

function mapAuditEvent(
  entry: AuditListOut["items"][number],
  titleByRequestId: Map<string, string>,
): AuditFeedEvent {
  return {
    id: `${entry.request_id}-${entry.id}`,
    timestamp: entry.timestamp,
    kind: parseAuditKind(entry.category),
    title: entry.message,
    description: entry.step_name
      ? `${entry.category} · ${entry.step_name}`
      : `${entry.category}`,
    caseId: entry.request_id,
    caseTitle: titleByRequestId.get(entry.request_id) ?? "Sourcing request",
    level: entry.level,
    category: entry.category,
    stepName: entry.step_name,
    source: entry.source,
    details: entry.details,
    runId: entry.run_id,
  }
}

function buildAuditFeedMeta({
  mode,
  source,
  totalKnown,
  fetchedCount,
  warning,
}: {
  mode: AuditFeedMeta["mode"]
  source: AuditFeedMeta["source"]
  totalKnown: number
  fetchedCount: number
  warning?: string
}): AuditFeedMeta {
  return {
    mode,
    source,
    totalKnown,
    fetchedCount,
    isTruncated: totalKnown > fetchedCount,
    asOf: new Date().toISOString(),
    ...(warning ? { warning } : {}),
  }
}

async function fetchAllAuditPages(): Promise<AuditListOut> {
  const items: AuditListOut["items"] = []
  let skip = 0
  let total = 0

  do {
    const page = (await chainIqApi.orgLogs.audit.list({
      skip,
      limit: AUDIT_PAGE_SIZE,
    })) as AuditListOut
    items.push(...page.items)
    total = Number.isFinite(page.total) ? page.total : items.length
    skip += AUDIT_PAGE_SIZE
  } while (skip < total)

  return { items, total }
}

async function fetchAuditListWithFallback(): Promise<AuditFetchResult> {
  try {
    const audit = await fetchAllAuditPages()
    return {
      audit,
      meta: buildAuditFeedMeta({
        mode: "fresh",
        source: "orgLogs",
        totalKnown: audit.total,
        fetchedCount: audit.items.length,
      }),
    }
  } catch (primaryError) {
    try {
      const fallbackAudit = (await chainIqApi.orgLogs.audit.list({
        limit: AUDIT_PAGE_SIZE,
      })) as AuditListOut
      const totalKnown = Number.isFinite(fallbackAudit.total)
        ? fallbackAudit.total
        : fallbackAudit.items.length
      return {
        audit: fallbackAudit,
        meta: buildAuditFeedMeta({
          mode: "degraded",
          source: "orgLogsFallback",
          totalKnown,
          fetchedCount: fallbackAudit.items.length,
          warning:
            "Primary audit feed pagination failed. Showing first page only.",
        }),
      }
    } catch {
      return {
        audit: { items: [], total: 0 },
        meta: buildAuditFeedMeta({
          mode: "degraded",
          source: "none",
          totalKnown: 0,
          fetchedCount: 0,
          warning: `Audit data is temporarily unavailable. ${fallbackReasonFromError(primaryError)}`,
        }),
      }
    }
  }
}

export async function getDashboardPageData(): Promise<DashboardPageData> {
  const nowMs = Date.now()
  if (dashboardSnapshot && isDashboardSnapshotFresh(dashboardSnapshot, nowMs)) {
    return toDashboardPageData(dashboardSnapshot, "fresh")
  }

  try {
    const snapshot = await loadDashboardSnapshotWithDeduping()
    return toDashboardPageData(snapshot, "fresh")
  } catch (error) {
    if (dashboardSnapshot) {
      return toDashboardPageData(
        dashboardSnapshot,
        "stale",
        fallbackReasonFromError(error),
      )
    }
    throw error
  }
}

export async function getDashboardMetrics(): Promise<DashboardMetric[]> {
  const rawData = await fetchDashboardRawData()
  return buildDashboardMetricsFromData(rawData)
}

export async function getCaseList(): Promise<CaseListItem[]> {
  const rawData = await fetchDashboardRawData()
  return buildCaseListFromData(rawData)
}

export interface CaseListPage {
  items: CaseListItem[]
  total: number
  skip: number
  limit: number
}

export async function getCaseListPage(params: {
  skip?: number
  limit?: number
  status?: string
}): Promise<CaseListPage> {
  const skip = params.skip ?? 0
  const limit = params.limit ?? 25

  const [requestsPage, categoriesMap, escalationRows] = await Promise.all([
    chainIqApi.requests.list({
      skip,
      limit,
      ...(params.status ? { status: params.status } : {}),
    }) as Promise<{ items: RequestRow[]; total: number; skip: number; limit: number }>,
    getCategoriesMap(),
    fetchEscalationQueueRows(),
  ])

  const escalationsByRequest = new Map<string, QueueEscalationItem[]>()
  for (const escalation of escalationRows) {
    const bucket = escalationsByRequest.get(escalation.caseId) ?? []
    bucket.push(escalation)
    escalationsByRequest.set(escalation.caseId, bucket)
  }

  const pipelineResults = await Promise.all(
    requestsPage.items.map((request) =>
      chainIqApi.pipelineResults
        .latest(request.request_id)
        .catch((): PipelineResultOut | null => null),
    ),
  )

  const items: CaseListItem[] = requestsPage.items.map((request, index) => {
    const pipelineResult = pipelineResults[index] ?? null
    const requestEscalations = escalationsByRequest.get(request.request_id) ?? []
    const status = normalizeStatus(request.status)

    const hasBlockingEscalation = requestEscalations.some(
      (entry) => entry.blocking && entry.status !== "resolved",
    )
    const hasEscalation = requestEscalations.some(
      (entry) => entry.status !== "resolved",
    )

    let recommendationStatus: RecommendationStatus
    if (pipelineResult?.recommendation_status) {
      const raw = pipelineResult.recommendation_status
      if (raw === "proceed" || raw === "proceed_with_conditions" || raw === "cannot_proceed") {
        recommendationStatus = raw
      } else {
        recommendationStatus = recommendationStatusFrom(hasBlockingEscalation, hasEscalation, status)
      }
    } else {
      recommendationStatus = recommendationStatusFrom(hasBlockingEscalation, hasEscalation, status)
    }

    const supplierLabel =
      pipelineResult?.summary?.top_supplier_name ??
      request.incumbent_supplier ??
      ""

    return {
      requestId: request.request_id,
      title: request.title,
      category: categoriesMap.get(request.category_id) ?? "",
      businessUnit: request.business_unit,
      countryLabel: request.country,
      budgetAmount: toNumber(request.budget_amount),
      currency: request.currency,
      requiredByDate: request.required_by_date,
      status,
      scenarioTags: normalizeTags(request.scenario_tags ?? []),
      recommendationStatus,
      escalationStatus: hasBlockingEscalation
        ? "blocking"
        : hasEscalation
          ? "advisory"
          : "none",
      lastUpdated: pipelineResult?.processed_at ?? request.created_at,
      supplierLabel,
      needsAttention:
        hasBlockingEscalation ||
        status === "pending_review" ||
        status === "escalated" ||
        (recommendationStatus !== "proceed" && recommendationStatus !== "not_evaluated"),
    }
  })

  return {
    items,
    total: requestsPage.total,
    skip: requestsPage.skip,
    limit: requestsPage.limit,
  }
}

export async function getCaseDetailByRunId(
  runId: string,
): Promise<{ caseDetail: CaseDetail; runId: string } | null> {
  const evaluation = await fetchEvaluationRunById(runId)
  if (!evaluation) return null

  const caseDetail = await getCaseDetail(evaluation.request_id)
  if (!caseDetail) return null

  return { caseDetail, runId: evaluation.run_id }
}

/** Aggregates request, analytics overview, awards, escalations, audit, and evaluation runs into the `CaseDetail` view model used by `CaseWorkspace`. */
export async function getCaseDetail(caseId: string): Promise<CaseDetail | null> {
  let detail: RequestDetail
  try {
    detail = (await chainIqApi.requests.get(caseId)) as RequestDetail
  } catch (error) {
    if (isNotFoundError(error)) {
      return null
    }
    throw error
  }

  const [overview, awards, escalationRows, auditLogs, auditSummary, evaluationRunsRaw, pipelineResult] = await Promise.all([
    chainIqApi.analytics.requestOverview(caseId) as Promise<RequestOverview>,
    chainIqApi.awards.byRequest(caseId) as Promise<HistoricalAward[]>,
    fetchEscalationRowsByRequest(caseId),
    fetchCaseAuditLogs(caseId),
    fetchCaseAuditSummary(caseId),
    fetchEvaluationRunsByRequest(caseId),
    chainIqApi.pipelineResults.latest(caseId).catch((): PipelineResultOut | null => null),
  ])

  const pipelineOutput = pipelineResult?.output as Record<string, unknown> | null | undefined
  const pipelineShortlistRaw = Array.isArray(pipelineOutput?.supplier_shortlist)
    ? (pipelineOutput.supplier_shortlist as Record<string, unknown>[])
    : null
  const pipelineRecommendation = pipelineOutput?.recommendation as Record<string, unknown> | null | undefined

  let shortlist: SupplierRow[]

  if (pipelineShortlistRaw && pipelineShortlistRaw.length > 0) {
    shortlist = pipelineShortlistRaw.map((entry, i) =>
      mapSupplierShortlistEntry(entry, i),
    )
  } else {
    const pricingBySupplier = new Map(
      overview.pricing.map((entry) => [entry.supplier_id, entry]),
    )

    shortlist = overview.compliant_suppliers
      .map((supplier) => {
        const pricing = pricingBySupplier.get(supplier.supplier_id)
        if (!pricing) return null

        return {
          supplierId: supplier.supplier_id,
          supplierName: supplier.supplier_name,
          countryHq: supplier.country_hq,
          currency: supplier.currency,
          preferred: supplier.preferred_supplier,
          incumbent: supplier.supplier_name === detail.incumbent_supplier,
          pricingTierApplied: pricing.pricing_id,
          region: pricing.region,
          minQuantity: pricing.min_quantity,
          maxQuantity: pricing.max_quantity,
          moq: pricing.moq,
          unitPrice: toNumber(pricing.unit_price) ?? 0,
          totalPrice: toNumber(pricing.total_price) ?? 0,
          standardLeadTimeDays: pricing.standard_lead_time_days,
          expeditedLeadTimeDays: pricing.expedited_lead_time_days,
          expeditedUnitPrice: toNumber(pricing.expedited_unit_price) ?? 0,
          expeditedTotal: toNumber(pricing.expedited_total_price) ?? 0,
          qualityScore: supplier.quality_score,
          riskScore: supplier.risk_score,
          esgScore: supplier.esg_score,
          policyCompliant: true,
          coversDeliveryCountry: true,
          dataResidencySupported: supplier.data_residency_supported,
          recommendationNote:
            "Eligible supplier after policy and region checks.",
        }
      })
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null)
      .sort((a, b) => a.totalPrice - b.totalPrice)
      .map((entry, index) => ({ ...entry, rank: index + 1 }))
  }

  const pipelineExcludedRaw = Array.isArray(pipelineOutput?.suppliers_excluded)
    ? (pipelineOutput.suppliers_excluded as Array<Record<string, unknown>>)
    : null

  let excludedSuppliers: CaseDetail["excludedSuppliers"]
  if (pipelineExcludedRaw && pipelineExcludedRaw.length > 0) {
    excludedSuppliers = pipelineExcludedRaw.map((entry) => ({
      supplierId: (entry.supplier_id as string) ?? "",
      supplierName: (entry.supplier_name as string) ?? "",
      reason: (entry.reason as string) ?? "Excluded by pipeline",
      hardExclusion: ((entry.reason as string) ?? "").toLowerCase().includes("restricted"),
    }))
  } else {
    const shortlistIds = new Set(shortlist.map((entry) => entry.supplierId))
    excludedSuppliers = awards
      .filter((entry) => !shortlistIds.has(entry.supplier_id) && !entry.awarded)
      .map((entry) => ({
        supplierId: entry.supplier_id,
        supplierName: entry.supplier_name,
        reason: entry.decision_rationale,
        hardExclusion: !entry.policy_compliant || entry.escalation_required,
      }))
  }

  const latestRunId = auditLogs.items.length > 0
    ? auditLogs.items.reduce((latest, entry) => {
        if (!entry.run_id) return latest
        if (!latest) return entry
        return new Date(entry.timestamp) > new Date(latest.timestamp) ? entry : latest
      }, null as (typeof auditLogs.items)[number] | null)?.run_id ?? null
    : null

  const latestRunItems = latestRunId
    ? auditLogs.items.filter((entry) => entry.run_id === latestRunId)
    : auditLogs.items

  const validationIssues = latestRunItems
    .filter((entry) => entry.category === "validation")
    .map((entry, index) => {
      const details = asRecord(entry.details)
      const severity = details?.severity as string | undefined
      const issueType = (details?.issue_type as string | undefined)?.trim()
      const issueField = (details?.field as string | undefined)?.trim()
      const issueLabel = issueType ? issueType.toUpperCase() : `VAL-${index + 1}`
      const issueId = issueField ? `${issueLabel} · ${issueField}` : issueLabel
      return {
        issueKey: `validation-${entry.id}`,
        issueId,
        severity: severityFrom(severity),
        type: entry.category,
        description: entry.message,
        actionRequired:
          (details?.action_required as string | undefined) ??
          "Review validation findings and update request input.",
        blocking: severity === "critical" || severity === "high",
        auditRowId: entry.id,
        runId: entry.run_id,
        timestamp: entry.timestamp,
        stepName: entry.step_name,
        level: entry.level,
        source: entry.source,
        details: details,
      }
    })

  const escalations: CaseDetail["escalations"] = escalationRows.map((entry) => ({
    escalationId: entry.escalationId,
    rule: entry.ruleId,
    ruleLabel: entry.ruleLabel,
    trigger: entry.trigger,
    escalateTo: entry.escalateTo,
    blocking: entry.blocking,
    status: entry.status,
    nextAction:
      entry.status === "resolved"
        ? "Escalation resolved with documented outcome."
        : entry.blocking
          ? `Coordinate decision with ${entry.escalateTo}.`
          : `Document advisory input from ${entry.escalateTo}.`,
  }))

  const hasBlockingValidation = validationIssues.some((issue) => issue.blocking)
  const hasBlockingEscalation = escalations.some(
    (entry) => entry.blocking && entry.status !== "resolved",
  )
  const hasEscalation = escalations.some((entry) => entry.status !== "resolved")
  const status = normalizeStatus(detail.status)

  let recommendationStatus: RecommendationStatus
  if (pipelineResult?.recommendation_status) {
    const raw = pipelineResult.recommendation_status
    if (raw === "proceed" || raw === "proceed_with_conditions" || raw === "cannot_proceed") {
      recommendationStatus = raw
    } else {
      recommendationStatus = recommendationStatusFrom(
        hasBlockingValidation || hasBlockingEscalation || shortlist.length === 0,
        hasEscalation,
        status,
      )
    }
  } else {
    recommendationStatus = recommendationStatusFrom(
      hasBlockingValidation || hasBlockingEscalation || shortlist.length === 0,
      hasEscalation,
      status,
    )
  }

  const topSupplier = shortlist[0]

  const policyCards = [
    ...overview.applicable_rules.category_rules.map((rule, index) => ({
      title: "Category Policy",
      ruleId: String(rule.rule_id ?? `CATEGORY-${index + 1}`),
      status: "informative" as const,
      summary: String(rule.rule_text ?? "Category rule applied."),
      detail: [
        {
          label: "Rule Type",
          value: String(rule.rule_type ?? "category_policy"),
        },
      ],
    })),
    ...overview.applicable_rules.geography_rules.map((rule, index) => ({
      title: "Geography Policy",
      ruleId: String(rule.rule_id ?? `GEO-${index + 1}`),
      status: "informative" as const,
      summary: String(rule.rule_text ?? "Geography rule applied."),
      detail: [
        { label: "Country", value: String(rule.country ?? "Regional") },
        { label: "Region", value: String(rule.region ?? "N/A") },
      ],
    })),
  ]

  const deliveryCountries =
    detail.delivery_countries.map((entry) => entry.country_code) || []

  const interpretedRequirements = [
    {
      label: "Category",
      value: `${detail.category_l1 ?? "Unknown"} / ${detail.category_l2 ?? "Unknown"}`,
      emphasis: true,
    },
    {
      label: "Quantity",
      value: `${toNumber(detail.quantity) ?? "Not provided"} ${detail.unit_of_measure}`,
      inferred: detail.quantity === null,
    },
    {
      label: "Budget",
      value:
        toNumber(detail.budget_amount) === null
          ? "Not provided"
          : `${detail.currency} ${toNumber(detail.budget_amount)}`,
      inferred: detail.budget_amount === null,
    },
    {
      label: "Delivery countries",
      value: deliveryCountries.length > 0 ? deliveryCountries.join(", ") : detail.country,
    },
    {
      label: "Data residency",
      value: detail.data_residency_constraint ? "Required" : "Not required",
    },
    {
      label: "ESG requirement",
      value: detail.esg_requirement ? "Required" : "Not required",
    },
  ]

  const timeline = auditLogs.items
    .map((entry) => ({
      id: `${entry.request_id}-${entry.id}`,
      timestamp: entry.timestamp,
      title: entry.message,
      description: entry.step_name
        ? `${entry.category} · ${entry.step_name}`
        : entry.category,
      kind: parseAuditKind(entry.category),
      level: entry.level,
      category: entry.category,
      stepName: entry.step_name,
      source: entry.source,
      details: asRecord(entry.details),
    }))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

  const scenarioTags = detail.scenario_tags
    .map((entry) =>
      typeof entry === "string" ? entry : (entry as { tag?: string }).tag ?? "",
    )
    .filter(Boolean)

  const evaluationRuns = evaluationRunsRaw.map(mapEvaluationRunDetail)

  return {
    id: caseId,
    title: detail.title,
    outcomeLabel:
      recommendationStatus === "not_evaluated"
        ? "Not evaluated"
        : recommendationStatus === "proceed"
          ? "Proceed"
          : recommendationStatus === "proceed_with_conditions"
            ? "Proceed with conditions"
            : "Cannot proceed",
    rawRequest: {
      requestId: detail.request_id,
      categoryId: detail.category_id,
      createdAt: detail.created_at,
      requestChannel:
        detail.request_channel === "teams" || detail.request_channel === "email"
          ? detail.request_channel
          : "portal",
      requestLanguage: detail.request_language,
      businessUnit: detail.business_unit,
      country: detail.country,
      site: detail.site,
      requesterId: detail.requester_id,
      requesterRole: detail.requester_role ?? "Not specified",
      submittedForId: detail.submitted_for_id,
      status,
      scenarioTags: normalizeTags(scenarioTags),
      categoryL1: detail.category_l1 ?? "Unknown",
      categoryL2: detail.category_l2 ?? "Unknown",
      title: detail.title,
      requestText: detail.request_text,
      currency: detail.currency,
      budgetAmount: toNumber(detail.budget_amount),
      quantity: toNumber(detail.quantity),
      unitOfMeasure: detail.unit_of_measure,
      requiredByDate: detail.required_by_date,
      deliveryCountries,
      dataResidencyConstraint: detail.data_residency_constraint,
      esgRequirement: detail.esg_requirement,
      preferredSupplierMentioned: detail.preferred_supplier_mentioned,
      incumbentSupplier: detail.incumbent_supplier,
      contractTypeRequested: detail.contract_type_requested,
    },
    recommendation: {
      status: recommendationStatus,
      reason:
        pipelineRecommendation?.reason as string ??
        (recommendationStatus === "not_evaluated"
          ? "This request has not been processed through the pipeline yet."
          : recommendationStatus === "proceed"
            ? "Supplier shortlist satisfies the current policy checks."
            : "Case requires additional human validation before final award."),
      recommendedSupplier:
        topSupplier?.supplierName ??
        (pipelineResult?.summary?.top_supplier_name as string | null) ??
        null,
      preferredSupplierIfResolved:
        (pipelineRecommendation?.preferred_supplier_if_resolved as string | null) ??
        overview.compliant_suppliers.find((entry) => entry.preferred_supplier)
          ?.supplier_name ?? null,
      rationale:
        (pipelineRecommendation?.preferred_supplier_rationale as string | null) ??
        topSupplier?.recommendationNote ??
        "No compliant supplier meets all constraints yet.",
      totalPrice: topSupplier?.totalPrice ?? null,
      minimumBudgetRequired:
        toNumber(pipelineRecommendation?.minimum_budget_required as number | null) ??
        topSupplier?.totalPrice ?? null,
      currency: detail.currency,
      approvalTier: overview.approval_tier?.threshold_id ?? "Threshold unavailable",
      minAmount: toNumber(overview.approval_tier?.min_amount),
      maxAmount: toNumber(overview.approval_tier?.max_amount ?? null),
      managers: overview.approval_tier?.managers ?? [],
      deviationApprovers: overview.approval_tier?.deviation_approvers ?? [],
      policyNote: overview.approval_tier?.policy_note ?? null,
      quotesRequired: overview.approval_tier?.min_supplier_quotes ?? 0,
      complianceStatus:
        recommendationStatus === "not_evaluated"
          ? "Not evaluated"
          : recommendationStatus === "cannot_proceed"
            ? "Blocked"
            : recommendationStatus === "proceed_with_conditions"
              ? "Conditional"
              : "Compliant",
      confidenceScore: pipelineResult?.summary?.confidence_score ?? null,
      supplierCount: pipelineResult?.summary?.supplier_count ?? shortlist.length,
      excludedCount: pipelineResult?.summary?.excluded_count ?? 0,
      escalationCount: pipelineResult?.summary?.escalation_count ?? escalations.length,
      blockingEscalationCount: pipelineResult?.summary?.blocking_escalation_count ?? 0,
      hasPipelineResult: pipelineResult !== null,
    },
    interpretedRequirements,
    validationIssues,
    policyCards,
    supplierShortlist: shortlist,
    excludedSuppliers,
    evaluationRuns,
    escalations,
    auditTrail: {
      policiesChecked:
        auditSummary.distinct_policies.length > 0
          ? auditSummary.distinct_policies
          : policyCards.map((entry) => entry.ruleId),
      supplierIdsEvaluated:
        auditSummary.distinct_suppliers.length > 0
          ? auditSummary.distinct_suppliers
          : overview.compliant_suppliers.map((entry) => entry.supplier_id),
      pricingTiersApplied:
        overview.pricing.map((entry) => entry.pricing_id).join(", ") || "None",
      dataSourcesUsed: [
        "requests",
        "analytics.request-overview",
        "awards",
        "escalations",
        "logs.audit",
      ],
      historicalAwardsConsulted: awards.length > 0,
      historicalAwardNote:
        awards.length > 0
          ? `${awards.length} historical award rows referenced.`
          : "No historical awards for this request.",
      reasoningTrace:
        latestRunItems.length > 0
          ? latestRunItems.slice(0, 8).map((entry) => entry.message)
          : [
              "Parse and validate request fields (budget, quantity, delivery scope).",
              "Apply category and geography policy constraints.",
              "Build compliant supplier shortlist and price by tier.",
              "Determine approval tier and escalation requirements.",
            ],
      timeline,
    },
    historicalPrecedent:
      awards.length > 0
        ? {
            title: "Historical precedent",
            description:
              "Award history for this request context used for audit comparability.",
            metrics: [
              {
                label: "Award rows",
                value: awards.length.toString(),
              },
              {
                label: "Best savings",
                value: `${Math.max(...awards.map((entry) => toNumber(entry.savings_pct) ?? 0)).toFixed(2)}%`,
              },
              {
                label: "Fastest lead time",
                value: `${Math.min(...awards.map((entry) => entry.lead_time_days))} days`,
              },
            ],
          }
        : undefined,
    lastUpdated:
      auditSummary.last_event ??
      timeline.at(-1)?.timestamp ??
      new Date().toISOString(),
  }
}

export async function getEscalationQueue(): Promise<QueueEscalationItem[]> {
  const escalationRows = await fetchEscalationQueueRows()
  return escalationRows.sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  )
}

export async function getAuditPageData(): Promise<AuditPageData> {
  const [requests, escalationRows, auditResult] = await Promise.all([
    getAllRequests(),
    fetchEscalationQueueRows(),
    fetchAuditListWithFallback(),
  ])

  const titleByRequestId = new Map(
    requests.map((entry) => [entry.request_id, entry.title]),
  )

  const feed = auditResult.audit.items
    .map((entry) => mapAuditEvent(entry, titleByRequestId))
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())

  const casesWithTrace = new Set(
    auditResult.audit.items.map((entry) => entry.request_id).filter(Boolean),
  )
  const policyConflicts = auditResult.audit.items.filter(
    (entry) => entry.category === "policy" && entry.level === "error",
  )

  const summary: AuditSummaryMetric[] = [
    {
      label: "Cases With Audit Trace",
      value: casesWithTrace.size.toString(),
      helper: `${casesWithTrace.size} of ${requests.length} requests have captured audit events.`,
    },
    {
      label: "Audit Entries",
      value: auditResult.meta.totalKnown.toString(),
      helper: auditResult.meta.isTruncated
        ? `Showing ${auditResult.meta.fetchedCount} of ${auditResult.meta.totalKnown} entries.`
        : `${auditResult.meta.totalKnown} structured pipeline events available for review.`,
    },
    {
      label: "Escalations In Queue",
      value: escalationRows.length.toString(),
      helper: "Open and resolved escalation objects produced by policy logic.",
    },
    {
      label: "Policy Conflicts",
      value: policyConflicts.length.toString(),
      helper: "Audit events flagged as policy-level errors.",
    },
  ]

  return {
    summary,
    feed,
    feedMeta: auditResult.meta,
  }
}

export async function getAuditFeed(): Promise<AuditFeedEvent[]> {
  return (await getAuditPageData()).feed
}

export async function getAuditOverview(): Promise<{
  summary: AuditSummaryMetric[]
  feedMeta: AuditFeedMeta
}> {
  const data = await getAuditPageData()
  return {
    summary: data.summary,
    feedMeta: data.feedMeta,
  }
}

const INTAKE_REQUIRED_FIELDS: Array<keyof CaseDraftPayload> = [
  "title",
  "requestText",
  "requestChannel",
  "requestLanguage",
  "businessUnit",
  "country",
  "site",
  "requesterId",
  "submittedForId",
  "categoryId",
  "unitOfMeasure",
  "currency",
  "requiredByDate",
  "contractTypeRequested",
]

function getApiUrlCandidates(path: string): string[] {
  const normalized = path.startsWith("/") ? path : `/${path}`
  // Browser runtime must only use same-origin paths.
  if (typeof window !== "undefined") {
    return [normalized]
  }
  const internalBase = process.env.BACKEND_INTERNAL_URL
  if (internalBase) {
    return [normalized, `${internalBase}${normalized}`]
  }
  return [normalized]
}

async function fetchMutation<T>(path: string, init: RequestInit): Promise<T> {
  const candidates = getApiUrlCandidates(path)
  let lastError: unknown = null

  for (const url of candidates) {
    try {
      const response = await fetch(url, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(init.headers ?? {}),
        },
      })
      if (!response.ok) {
        lastError = new Error(`Request failed (${response.status}) for ${path}`)
        continue
      }
      return response.json() as Promise<T>
    } catch (error) {
      lastError = error
    }
  }

  if (lastError instanceof Error && lastError.message.trim()) {
    throw lastError
  }
  throw new Error(`Request failed for ${path}`)
}

function createRequestId() {
  const stamp = Date.now().toString().slice(-8)
  const random = Math.floor(Math.random() * 10_000)
    .toString()
    .padStart(4, "0")
  return `REQ-${stamp}${random}`
}

function defaultRequiredByDate() {
  const value = new Date()
  value.setDate(value.getDate() + 14)
  return value.toISOString().slice(0, 10)
}

function defaultDraftFromIntake(input: CaseIntakeInput): CaseDraftPayload {
  const sourceText = input.sourceText.trim()
  const firstLine =
    sourceText.split("\n").find((line) => line.trim().length > 0)?.trim() ??
    "New sourcing case"

  return {
    title: firstLine.slice(0, 120),
    requestText: sourceText,
    requestChannel: input.requestChannel ?? "portal",
    requestLanguage: "en",
    businessUnit: "General",
    country: "CH",
    site: "HQ",
    requesterId: "UNKNOWN",
    requesterRole: "Not specified",
    submittedForId: "SELF",
    categoryId: null,
    quantity: null,
    unitOfMeasure: "unit",
    currency: "CHF",
    budgetAmount: null,
    requiredByDate: defaultRequiredByDate(),
    deliveryCountries: [],
    preferredSupplierMentioned: null,
    incumbentSupplier: null,
    contractTypeRequested: "one_time",
    dataResidencyConstraint: false,
    esgRequirement: false,
    requesterInstruction: input.note?.trim() || null,
    scenarioTags: [],
    status: "new",
  }
}

function isPresentValue(value: unknown) {
  if (value === null || value === undefined) return false
  if (typeof value === "string") return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  return true
}

export function computeMissingRequiredFields(
  draft: CaseDraftPayload,
): Array<keyof CaseDraftPayload> {
  return INTAKE_REQUIRED_FIELDS.filter((field) => !isPresentValue(draft[field]))
}

type CategoryApiRow = {
  id: number
  category_l1: string
  category_l2: string
}

export async function getCategoryOptions(): Promise<CategoryOption[]> {
  const requestUrls = getApiUrlCandidates("/api/categories/")
  let response: Response | null = null
  let lastError: unknown = null

  for (const url of requestUrls) {
    try {
      response = await fetch(url, { cache: "no-store" })
      if (response.ok) break
      lastError = new Error(`Request failed (${response.status}) for /api/categories/`)
    } catch (error) {
      lastError = error
    }
  }

  if (!response || !response.ok) {
    if (lastError instanceof Error && lastError.message.trim()) {
      throw lastError
    }
    throw new Error("Request failed for /api/categories/")
  }

  const rows = (await response.json()) as CategoryApiRow[]
  return rows.map((row) => ({
    id: row.id,
    categoryL1: row.category_l1,
    categoryL2: row.category_l2,
  }))
}

type ExtractionResponse = {
  draft: Record<string, unknown>
  field_status: Record<string, { status: string; confidence: number; reason?: string }>
  missing_required: string[]
  warnings: Array<{ code: string; severity: Severity; message: string }>
  extraction_strength: "strong" | "partial" | "low"
}

type ParseResponse = {
  complete: boolean
  request: Record<string, unknown>
}

function extractionStrength(
  missingRequiredCount: number,
  confidentFieldsCount: number,
): "strong" | "partial" | "low" {
  if (missingRequiredCount === 0 && confidentFieldsCount >= 8) return "strong"
  if (confidentFieldsCount >= 4) return "partial"
  return "low"
}

function normalizeRequiredByDate(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.trim()) {
    const trimmed = value.trim()
    if (/^\d{4}-\d{2}-\d{2}/.test(trimmed)) {
      return trimmed.slice(0, 10)
    }
    const parsed = new Date(trimmed)
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString().slice(0, 10)
    }
  }
  return fallback
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter(Boolean)
}

function toNumberFromUnknown(value: unknown): number | null {
  if (typeof value === "number" || typeof value === "string") {
    return toNumber(value)
  }
  return null
}

function normalizeIntakeResponse(
  response: ExtractionResponse,
  fallbackDraft: CaseDraftPayload,
  fallbackUsed: boolean,
): ExtractionResult {
  const mergedDraft: CaseDraftPayload = {
    ...fallbackDraft,
    ...(response.draft as Partial<CaseDraftPayload>),
    scenarioTags: Array.isArray(response.draft.scenarioTags)
      ? (response.draft.scenarioTags as ScenarioTag[])
      : fallbackDraft.scenarioTags,
    deliveryCountries: Array.isArray(response.draft.deliveryCountries)
      ? (response.draft.deliveryCountries as string[])
      : fallbackDraft.deliveryCountries,
  }

  const fieldStatus: ExtractionResult["fieldStatus"] = {}
  for (const [key, value] of Object.entries(response.field_status)) {
    fieldStatus[key as keyof CaseDraftPayload] = {
      status:
        value.status === "confident" ||
        value.status === "inferred" ||
        value.status === "missing" ||
        value.status === "needs_review"
          ? value.status
          : "needs_review",
      confidence: value.confidence,
      reason: value.reason,
    }
  }

  return {
    draft: mergedDraft,
    fieldStatus,
    missingRequired:
      response.missing_required.length > 0
        ? (response.missing_required as Array<keyof CaseDraftPayload>)
        : computeMissingRequiredFields(mergedDraft),
    warnings: response.warnings,
    extractionStrength: response.extraction_strength,
    fallbackUsed,
  }
}

async function extractViaIntakeApi(
  payload: CaseIntakeInput,
  fallbackDraft: CaseDraftPayload,
  fallbackUsed: boolean,
): Promise<ExtractionResult> {
  console.info("[extractCaseInput] calling /api/intake/extract", {
    sourceType: payload.sourceType,
    sourceTextLength: payload.sourceText.length,
    noteLength: payload.note?.length ?? 0,
    requestChannel: payload.requestChannel ?? null,
    fileNames: payload.files?.map((file) => file.name) ?? [],
    fallbackUsed,
  })
  const response = await fetchMutation<ExtractionResponse>("/api/intake/extract", {
    method: "POST",
    body: JSON.stringify({
      source_type: payload.sourceType,
      source_text: payload.sourceText,
      note: payload.note ?? null,
      request_channel: payload.requestChannel ?? null,
      file_names: payload.files?.map((file) => file.name) ?? [],
    }),
  })

  console.info("[extractCaseInput] /api/intake/extract response", {
    extractionStrength: response.extraction_strength,
    missingRequiredCount: response.missing_required.length,
    warningCodes: response.warnings.map((warning) => warning.code),
    draftKeys: Object.keys(response.draft),
  })

  return normalizeIntakeResponse(response, fallbackDraft, fallbackUsed)
}

function mapParsedDraft(
  payload: CaseIntakeInput,
  fallbackDraft: CaseDraftPayload,
  parseResponse: ParseResponse,
): ExtractionResult {
  const parsed = parseResponse.request ?? {}
  const categoryL1 =
    typeof parsed.category_l1 === "string" && parsed.category_l1.trim()
      ? parsed.category_l1.trim()
      : null
  const categoryL2 =
    typeof parsed.category_l2 === "string" && parsed.category_l2.trim()
      ? parsed.category_l2.trim()
      : null

  const mappedDraft = {
    ...fallbackDraft,
    title:
      typeof parsed.title === "string" && parsed.title.trim()
        ? parsed.title.trim()
        : fallbackDraft.title,
    requestText:
      typeof parsed.request_text === "string"
        ? parsed.request_text
        : fallbackDraft.requestText,
    requestChannel:
      typeof parsed.request_channel === "string" &&
      (parsed.request_channel === "portal" ||
        parsed.request_channel === "email" ||
        parsed.request_channel === "teams")
        ? parsed.request_channel
        : fallbackDraft.requestChannel,
    requestLanguage:
      typeof parsed.request_language === "string" && parsed.request_language.trim()
        ? parsed.request_language.trim()
        : fallbackDraft.requestLanguage,
    businessUnit:
      typeof parsed.business_unit === "string" && parsed.business_unit.trim()
        ? parsed.business_unit.trim()
        : fallbackDraft.businessUnit,
    country:
      typeof parsed.country === "string" && parsed.country.trim()
        ? parsed.country.trim().toUpperCase()
        : fallbackDraft.country,
    site:
      typeof parsed.site === "string" && parsed.site.trim()
        ? parsed.site.trim()
        : fallbackDraft.site,
    requesterId:
      typeof parsed.requester_id === "string" && parsed.requester_id.trim()
        ? parsed.requester_id.trim()
        : fallbackDraft.requesterId,
    requesterRole:
      typeof parsed.requester_role === "string" && parsed.requester_role.trim()
        ? parsed.requester_role.trim()
        : fallbackDraft.requesterRole,
    submittedForId:
      typeof parsed.submitted_for_id === "string" && parsed.submitted_for_id.trim()
        ? parsed.submitted_for_id.trim()
        : fallbackDraft.submittedForId,
    categoryId: toNumberFromUnknown(parsed.category_id),
    quantity: toNumberFromUnknown(parsed.quantity),
    unitOfMeasure:
      typeof parsed.unit_of_measure === "string" && parsed.unit_of_measure.trim()
        ? parsed.unit_of_measure.trim()
        : fallbackDraft.unitOfMeasure,
    currency:
      typeof parsed.currency === "string" && parsed.currency.trim()
        ? parsed.currency.trim().toUpperCase()
        : fallbackDraft.currency,
    budgetAmount: toNumberFromUnknown(parsed.budget_amount),
    requiredByDate: normalizeRequiredByDate(
      parsed.required_by_date,
      fallbackDraft.requiredByDate,
    ),
    deliveryCountries:
      normalizeStringArray(parsed.delivery_countries).length > 0
        ? normalizeStringArray(parsed.delivery_countries)
        : fallbackDraft.deliveryCountries,
    preferredSupplierMentioned:
      typeof parsed.preferred_supplier_mentioned === "string" &&
      parsed.preferred_supplier_mentioned.trim()
        ? parsed.preferred_supplier_mentioned.trim()
        : fallbackDraft.preferredSupplierMentioned,
    incumbentSupplier:
      typeof parsed.incumbent_supplier === "string" && parsed.incumbent_supplier.trim()
        ? parsed.incumbent_supplier.trim()
        : fallbackDraft.incumbentSupplier,
    contractTypeRequested:
      typeof parsed.contract_type_requested === "string" &&
      parsed.contract_type_requested.trim()
        ? parsed.contract_type_requested.trim()
        : fallbackDraft.contractTypeRequested,
    dataResidencyConstraint:
      typeof parsed.data_residency_constraint === "boolean"
        ? parsed.data_residency_constraint
        : fallbackDraft.dataResidencyConstraint,
    esgRequirement:
      typeof parsed.esg_requirement === "boolean"
        ? parsed.esg_requirement
        : fallbackDraft.esgRequirement,
    requesterInstruction: payload.note?.trim() || fallbackDraft.requesterInstruction,
    scenarioTags:
      normalizeStringArray(parsed.scenario_tags).length > 0
        ? normalizeStringArray(parsed.scenario_tags)
        : fallbackDraft.scenarioTags,
    status:
      typeof parsed.status === "string" && parsed.status.trim()
        ? parsed.status.trim()
        : fallbackDraft.status,
    categoryL1,
    categoryL2,
  } as CaseDraftPayload & { categoryL1: string | null; categoryL2: string | null }

  const parserKeyByField: Partial<Record<keyof CaseDraftPayload, string>> = {
    title: "title",
    requestText: "request_text",
    requestChannel: "request_channel",
    requestLanguage: "request_language",
    businessUnit: "business_unit",
    country: "country",
    site: "site",
    requesterId: "requester_id",
    submittedForId: "submitted_for_id",
    categoryId: "category_id",
    unitOfMeasure: "unit_of_measure",
    currency: "currency",
    requiredByDate: "required_by_date",
    contractTypeRequested: "contract_type_requested",
  }

  const fieldStatus: ExtractionResult["fieldStatus"] = {}
  for (const field of INTAKE_REQUIRED_FIELDS) {
    const parserKey = parserKeyByField[field]
    const hasDirectParsedValue = parserKey ? isPresentValue(parsed[parserKey]) : false
    const hasValue = isPresentValue(mappedDraft[field])
    fieldStatus[field] = {
      status: hasValue ? (hasDirectParsedValue ? "confident" : "inferred") : "missing",
      confidence: hasValue ? (hasDirectParsedValue ? 0.9 : 0.65) : 0,
      reason: hasValue
        ? hasDirectParsedValue
          ? "Directly extracted by the parser."
          : "Derived using defaults or intake metadata."
        : "Value not found in parser output.",
    }
  }

  const missingRequired = computeMissingRequiredFields(mappedDraft)
  const confidentFieldsCount = Object.values(fieldStatus).filter(
    (entry) => entry.status === "confident" || entry.status === "inferred",
  ).length

  return {
    draft: mappedDraft,
    fieldStatus,
    missingRequired,
    warnings: [],
    extractionStrength: extractionStrength(missingRequired.length, confidentFieldsCount),
    fallbackUsed: false,
  }
}

export async function extractCaseInput(
  payload: CaseIntakeInput,
): Promise<ExtractionResult> {
  const fallbackDraft = defaultDraftFromIntake(payload)
  console.info("[extractCaseInput] started", {
    sourceType: payload.sourceType,
    sourceTextLength: payload.sourceText.length,
    fileCount: payload.files?.length ?? 0,
    requestChannel: payload.requestChannel ?? null,
  })
  if (payload.sourceType === "upload") {
    if (!payload.files || payload.files.length === 0) {
      console.warn("[extractCaseInput] upload branch aborted: no files")
      throw new Error("Please select a file before analyzing upload input.")
    }
    try {
      const uploadContextText = payload.sourceText.trim() || undefined
      console.info("[extractCaseInput] upload branch calling parseFile", {
        fileName: payload.files[0].name,
        fileType: payload.files[0].type,
        fileSize: payload.files[0].size,
        contextTextLength: uploadContextText?.length ?? 0,
      })
      const parsed = (await chainIqApi.parse.parseFile(
        payload.files[0],
        payload.files[0].name,
        uploadContextText ? { contextText: uploadContextText } : undefined,
      )) as ParseResponse
      console.info("[extractCaseInput] parseFile response", {
        complete: parsed.complete,
        requestKeys: Object.keys(parsed.request ?? {}),
      })
      const mapped = mapParsedDraft(payload, fallbackDraft, parsed)
      console.info("[extractCaseInput] upload parse mapped", {
        extractionStrength: mapped.extractionStrength,
        missingRequiredCount: mapped.missingRequired.length,
        draftPreview: {
          title: mapped.draft.title,
          categoryId: mapped.draft.categoryId,
          currency: mapped.draft.currency,
          budgetAmount: mapped.draft.budgetAmount,
          quantity: mapped.draft.quantity,
        },
      })
      return mapped
    } catch (parseError) {
      console.warn("[extractCaseInput] parseFile failed, falling back", {
        error: parseError,
      })
      try {
        const heuristicResult = await extractViaIntakeApi(payload, fallbackDraft, true)
        console.info("[extractCaseInput] upload fallback succeeded", {
          extractionStrength: heuristicResult.extractionStrength,
          missingRequiredCount: heuristicResult.missingRequired.length,
          warningCodes: heuristicResult.warnings.map((warning) => warning.code),
        })
        return {
          ...heuristicResult,
          warnings: [
            {
              code: "UPLOAD_PARSE_FALLBACK",
              severity: "medium",
              message:
                "File parsing failed. Applied fallback extraction from available text and metadata.",
            },
            ...heuristicResult.warnings,
          ],
        }
      } catch (fallbackError) {
        console.error("[extractCaseInput] upload fallback failed", {
          error: fallbackError,
        })
        return {
          draft: fallbackDraft,
          fieldStatus: {
            requestText: {
              status: payload.sourceText.trim() ? "inferred" : "missing",
              confidence: payload.sourceText.trim() ? 0.7 : 0,
              reason: "Fallback extraction used because parser and intake API are unavailable.",
            },
          },
          missingRequired: computeMissingRequiredFields(fallbackDraft),
          warnings: [
            {
              code: "INTAKE_FALLBACK",
              severity: "medium",
              message:
                "Extraction service is unavailable. Continue with manual completion.",
            },
          ],
          extractionStrength: "low",
          fallbackUsed: true,
        }
      }
    }
  }

  try {
    console.info("[extractCaseInput] text/manual branch calling parseText", {
      sourceTextPreview: payload.sourceText.slice(0, 120),
    })
    const parsed = (await chainIqApi.parse.parseText({
      text: payload.sourceText,
    })) as ParseResponse
    console.info("[extractCaseInput] parseText response", {
      complete: parsed.complete,
      requestKeys: Object.keys(parsed.request ?? {}),
    })
    const result = mapParsedDraft(payload, fallbackDraft, parsed)
    console.info("[extractCaseInput] text/manual parser mapping succeeded", {
      extractionStrength: result.extractionStrength,
      missingRequiredCount: result.missingRequired.length,
      draftPreview: {
        title: result.draft.title,
        categoryId: result.draft.categoryId,
        currency: result.draft.currency,
        budgetAmount: result.draft.budgetAmount,
        quantity: result.draft.quantity,
      },
    })
    return result
  } catch (error) {
    console.warn("[extractCaseInput] parseText failed, falling back to heuristic intake route", {
      error,
    })
    try {
      const heuristicResult = await extractViaIntakeApi(payload, fallbackDraft, true)
      console.info("[extractCaseInput] heuristic fallback after parseText succeeded", {
        extractionStrength: heuristicResult.extractionStrength,
        missingRequiredCount: heuristicResult.missingRequired.length,
        warningCodes: heuristicResult.warnings.map((warning) => warning.code),
      })
      return {
        ...heuristicResult,
        warnings: [
          {
            code: "PARSE_TEXT_FALLBACK",
            severity: "medium",
            message:
              "Anthropic extraction failed. Applied heuristic extraction fallback.",
          },
          ...heuristicResult.warnings,
        ],
      }
    } catch (fallbackError) {
      console.error("[extractCaseInput] text/manual heuristic fallback failed", {
        error: fallbackError,
      })
      return {
        draft: fallbackDraft,
        fieldStatus: {
          requestText: {
            status: payload.sourceText.trim() ? "inferred" : "missing",
            confidence: payload.sourceText.trim() ? 0.7 : 0,
            reason: "Fallback extraction used because parser and intake API are unavailable.",
          },
        },
        missingRequired: computeMissingRequiredFields(fallbackDraft),
        warnings: [
          {
            code: "INTAKE_FALLBACK",
            severity: "medium",
            message:
              "Extraction service is unavailable. Continue with manual completion.",
          },
        ],
        extractionStrength: "low",
        fallbackUsed: true,
      }
    }
  }
}

type RequestMutationOut = { request_id: string }

function toRequestMutationPayload(payload: CaseDraftPayload) {
  return {
    request_id: payload.requestId,
    created_at: payload.createdAt,
    request_channel: payload.requestChannel,
    request_language: payload.requestLanguage,
    business_unit: payload.businessUnit,
    country: payload.country,
    site: payload.site,
    requester_id: payload.requesterId,
    requester_role: payload.requesterRole || null,
    submitted_for_id: payload.submittedForId,
    category_id: payload.categoryId,
    title: payload.title,
    request_text: payload.requestText,
    currency: payload.currency,
    budget_amount: payload.budgetAmount,
    quantity: payload.quantity,
    unit_of_measure: payload.unitOfMeasure,
    required_by_date: payload.requiredByDate,
    preferred_supplier_mentioned: payload.preferredSupplierMentioned,
    incumbent_supplier: payload.incumbentSupplier,
    contract_type_requested: payload.contractTypeRequested,
    data_residency_constraint: payload.dataResidencyConstraint,
    esg_requirement: payload.esgRequirement,
    status: payload.status,
    delivery_countries: payload.deliveryCountries,
    scenario_tags: payload.scenarioTags,
  }
}

export async function createCase(
  payload: CreateCasePayload,
): Promise<{ requestId: string }> {
  const draft: CaseDraftPayload = {
    ...payload,
    requestId: payload.requestId ?? createRequestId(),
    createdAt: payload.createdAt ?? new Date().toISOString(),
  }

  const response = await fetchMutation<RequestMutationOut>("/api/requests/", {
    method: "POST",
    body: JSON.stringify(toRequestMutationPayload(draft)),
  })
  return { requestId: response.request_id }
}

export async function updateCaseDraft(
  requestId: string,
  payload: Partial<CaseDraftPayload>,
): Promise<{ requestId: string }> {
  const body = {
    request_channel: payload.requestChannel,
    request_language: payload.requestLanguage,
    business_unit: payload.businessUnit,
    country: payload.country,
    site: payload.site,
    requester_id: payload.requesterId,
    requester_role: payload.requesterRole,
    submitted_for_id: payload.submittedForId,
    category_id: payload.categoryId,
    title: payload.title,
    request_text: payload.requestText,
    currency: payload.currency,
    budget_amount: payload.budgetAmount,
    quantity: payload.quantity,
    unit_of_measure: payload.unitOfMeasure,
    required_by_date: payload.requiredByDate,
    preferred_supplier_mentioned: payload.preferredSupplierMentioned,
    incumbent_supplier: payload.incumbentSupplier,
    contract_type_requested: payload.contractTypeRequested,
    data_residency_constraint: payload.dataResidencyConstraint,
    esg_requirement: payload.esgRequirement,
    status: payload.status,
    delivery_countries: payload.deliveryCountries,
    scenario_tags: payload.scenarioTags,
  }

  await fetchMutation<RequestMutationOut>(`/api/requests/${requestId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  })
  return { requestId }
}
