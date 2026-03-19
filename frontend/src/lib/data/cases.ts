import type {
  AuditFeedEvent,
  CaseDetail,
  CaseListItem,
  CaseStatus,
  DashboardPageData,
  DashboardMetric,
  EvaluationRunDetail,
  QueueEscalationItem,
  RecommendationStatus,
  RuleCheckResult,
  ScenarioTag,
  SupplierRow,
} from "@/lib/types/case"

type RequestListResponse = {
  items: RequestRow[]
  total: number
  skip: number
  limit: number
}

type HistoricalAwardListResponse = {
  items: HistoricalAward[]
  total: number
  skip: number
  limit: number
}

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

type RequestDetail = Omit<RequestRow, "scenario_tags"> & {
  delivery_countries: Array<{ id: number; country_code: string }>
  scenario_tags: Array<{ id: number; tag: string }>
  category_l1: string | null
  category_l2: string | null
}

type CategoryRow = {
  id: number
  category_l1: string
  category_l2: string
}

type HistoricalAward = {
  award_id: string
  request_id: string
  award_date: string
  supplier_id: string
  supplier_name: string
  total_value: string | number
  currency: string
  awarded: boolean
  award_rank: number
  decision_rationale: string
  policy_compliant: boolean
  escalation_required: boolean
  escalated_to: string | null
  savings_pct: string | number
  lead_time_days: number
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
    category_rules: Array<{
      rule_id: string
      rule_type: string
      rule_text: string
    }>
    geography_rules: Array<{
      rule_id: string
      rule_type: string | null
      rule_text: string
      region: string | null
      country: string | null
    }>
  }
  approval_tier: {
    threshold_id: string
    currency: string
    min_supplier_quotes: number
    policy_note: string | null
    managers: string[]
    deviation_approvers: string[]
  } | null
  historical_awards: Array<{
    award_id: string
    supplier_id: string
    supplier_name: string
    total_value: string | number
    currency: string
    awarded: boolean
    award_rank: number
    decision_rationale: string
    savings_pct: string | number
    lead_time_days: number
  }>
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

type EvaluationDetailApi = {
  run_id: string
  request_id: string
  status: string
  started_at: string
  finished_at: string | null
  favorite?: boolean
  supplier_shortlist?: Array<Record<string, unknown>>
  suppliers_excluded?: Array<{ supplier_id: string; supplier_name: string; reason: string }>
  supplier_breakdowns: Array<{
    supplier_id: string
    supplier_name: string | null
    hard_rule_checks: Array<{
      check_id: string
      rule_id: string
      version_id: string
      supplier_id: string | null
      result: string
      evidence?: Record<string, unknown> | null
      skipped?: boolean | null
      skip_reason?: string | null
      checked_at: string
    }>
    policy_checks: Array<{
      check_id: string
      rule_id: string
      version_id: string
      supplier_id: string | null
      result: string
      evidence?: Record<string, unknown> | null
      skipped?: boolean | null
      skip_reason?: string | null
      checked_at: string
    }>
    excluded: boolean
    exclusion_rule_id: string | null
    exclusion_reason: string | null
  }>
}

const backendInternalUrl = process.env.BACKEND_INTERNAL_URL
if (!backendInternalUrl) {
  throw new Error("BACKEND_INTERNAL_URL is required for backend data fetching.")
}

const BASE_API_URL = backendInternalUrl.replace(/\/$/, "")
const DASHBOARD_CACHE_TTL_MS = 15_000

const STATUS_MAP: Record<string, CaseStatus> = {
  new: "received",
  submitted: "parsed",
  pending_review: "pending_review",
  evaluated: "evaluated",
  recommended: "recommended",
  escalated: "escalated",
  resolved: "resolved",
  received: "received",
  parsed: "parsed",
}

const SCENARIO_TAGS = new Set<ScenarioTag>([
  "standard",
  "threshold",
  "lead_time",
  "missing_info",
  "contradictory",
  "restricted",
  "multilingual",
  "capacity",
  "multi_country",
])

class BackendApiError extends Error {
  status: number
  path: string

  constructor(path: string, status: number, detail: string) {
    super(`Backend request failed (${status}) for ${path}: ${detail}`)
    this.name = "BackendApiError"
    this.status = status
    this.path = path
  }
}

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeStatus(status: string): CaseStatus {
  return STATUS_MAP[status] ?? "received"
}

function normalizeTag(tag: string): ScenarioTag | null {
  return SCENARIO_TAGS.has(tag as ScenarioTag) ? (tag as ScenarioTag) : null
}

function normalizeTags(tags: string[]): ScenarioTag[] {
  return tags
    .map(normalizeTag)
    .filter((tag): tag is ScenarioTag => tag !== null)
}

function recommendationStatusFrom(
  hasBlocking: boolean,
  hasEscalation: boolean,
  status: CaseStatus,
): RecommendationStatus {
  if (hasBlocking) return "cannot_proceed"
  if (hasEscalation || status === "pending_review" || status === "escalated") {
    return "proceed_with_conditions"
  }
  return "proceed"
}

function getRequestUrl(path: string): string {
  return `${BASE_API_URL}${path}`
}

async function fetchJson<T>(path: string): Promise<T> {
  const url = getRequestUrl(path)
  const response = await fetch(url, { cache: "no-store" })
  if (!response.ok) {
    let detail = response.statusText || "Unknown backend error"
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) {
        detail = payload.detail
      }
    } catch {
      // Keep status text when backend response is not JSON.
    }
    throw new BackendApiError(path, response.status, detail)
  }

  return response.json() as Promise<T>
}

async function fetchAllPagedItems<T extends { total: number; skip: number; limit: number; items: U[] }, U>(
  basePath: string,
  limit = 200,
): Promise<U[]> {
  let skip = 0
  let total = 0
  const items: U[] = []

  do {
    const separator = basePath.includes("?") ? "&" : "?"
    const page = await fetchJson<T>(`${basePath}${separator}skip=${skip}&limit=${limit}`)
    items.push(...page.items)
    total = page.total
    skip += page.limit
  } while (skip < total)

  return items
}

async function getCategoriesMap() {
  const categories = await fetchJson<CategoryRow[]>("/api/categories/")
  return new Map<number, string>(
    categories.map((category) => [
      category.id,
      `${category.category_l1} / ${category.category_l2}`,
    ]),
  )
}

async function getAllRequests() {
  return await fetchAllPagedItems<RequestListResponse, RequestRow>("/api/requests/")
}

async function getAllAwards() {
  return await fetchAllPagedItems<HistoricalAwardListResponse, HistoricalAward>("/api/awards/")
}

type DashboardRawData = {
  requests: RequestRow[]
  awards: HistoricalAward[]
  categoriesMap: Map<number, string>
  escalationRows: QueueEscalationItem[]
}

type DashboardSnapshot = {
  metrics: DashboardMetric[]
  cases: CaseListItem[]
  asOf: string
  cachedAtMs: number
}

let dashboardSnapshot: DashboardSnapshot | null = null
let dashboardSnapshotPromise: Promise<DashboardSnapshot> | null = null

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

async function fetchEscalationQueueRows(): Promise<QueueEscalationItem[]> {
  const rows = await fetchJson<EscalationQueueApiRow[]>("/api/escalations/queue")
  return rows.map(mapEscalationQueueRow)
}

async function fetchEscalationRowsByRequest(
  requestId: string,
): Promise<QueueEscalationItem[]> {
  const rows = await fetchJson<EscalationQueueApiRow[]>(
    `/api/escalations/by-request/${requestId}`,
  )
  return rows.map(mapEscalationQueueRow)
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
  const totalPrice = extractPrice(entry, "total_price_") || extractPrice(entry, "total_price") || 0
  const unitPrice = extractPrice(entry, "unit_price_") || extractPrice(entry, "unit_price") || 0
  const expeditedTotal = extractPrice(entry, "expedited_total_") || extractPrice(entry, "expedited_total") || 0
  const expeditedUnitPrice = extractPrice(entry, "expedited_unit_price_") || extractPrice(entry, "expedited_unit_price") || 0
  return {
    rank: (entry.rank as number) ?? index + 1,
    supplierId: (entry.supplier_id as string) ?? "",
    supplierName: (entry.supplier_name as string) ?? "",
    preferred: (entry.preferred as boolean) ?? false,
    incumbent: (entry.incumbent as boolean) ?? false,
    pricingTierApplied: (entry.pricing_tier_applied as string) ?? "",
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
    recommendationNote: (entry.recommendation_note as string) ?? "Eligible supplier after policy and region checks.",
  }
}

function mapEvaluationRunDetail(raw: EvaluationDetailApi): EvaluationRunDetail {
  const supplierShortlist = (raw.supplier_shortlist ?? []).map((entry, i) =>
    mapSupplierShortlistEntry(entry as Record<string, unknown>, i),
  )
  const excludedSuppliersFromRun = (raw.suppliers_excluded ?? []).map((e) => ({
    supplierId: e.supplier_id,
    supplierName: e.supplier_name,
    reason: e.reason,
    hardExclusion: (e.reason ?? "").toLowerCase().includes("restricted"),
  }))
  return {
    runId: raw.run_id,
    requestId: raw.request_id,
    status: raw.status,
    startedAt: raw.started_at,
    finishedAt: raw.finished_at,
    favorite: raw.favorite ?? false,
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
        result: ((check.skipped ? "skipped" : check.result) ?? "skipped") as RuleCheckResult,
        checkedAt: check.checked_at,
        skipped: check.skipped ?? null,
        skipReason: check.skip_reason ?? null,
        evidence: check.evidence ?? null,
      })),
      policyChecks: entry.policy_checks.map((check) => ({
        checkId: check.check_id,
        ruleId: check.rule_id,
        versionId: check.version_id,
        supplierId: check.supplier_id,
        result: check.result as RuleCheckResult,
        checkedAt: check.checked_at,
        skipped: check.skipped ?? null,
        skipReason: check.skip_reason ?? null,
        evidence: check.evidence ?? null,
      })),
    })),
    supplierShortlist: supplierShortlist.length > 0 ? supplierShortlist : undefined,
    excludedSuppliersFromRun: excludedSuppliersFromRun.length > 0 ? excludedSuppliersFromRun : undefined,
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

function buildDashboardMetricsFromData({
  requests,
  awards,
  escalationRows,
}: Pick<DashboardRawData, "requests" | "awards" | "escalationRows">): DashboardMetric[] {
  const blockingCases = new Set(
    escalationRows
      .filter((entry) => entry.blocking && entry.status !== "resolved")
      .map((entry) => entry.caseId),
  )

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
    const winner = requestAwards.find((entry) => entry.awarded && entry.award_rank === 1)
    const fallbackSupplier = requestAwards.find((entry) => entry.award_rank === 1)

    return {
      requestId: request.request_id,
      title: request.title,
      category: categoriesMap.get(request.category_id) ?? "Unmapped category",
      businessUnit: request.business_unit,
      countryLabel: request.country,
      budgetAmount: toNumber(request.budget_amount),
      currency: request.currency,
      requiredByDate: request.required_by_date,
      status,
      scenarioTags: normalizedTags.length > 0 ? normalizedTags : ["standard"],
      recommendationStatus,
      escalationStatus: hasBlockingEscalation
        ? "blocking"
        : hasEscalation
          ? "advisory"
          : "none",
      lastUpdated: request.created_at,
      supplierLabel:
        winner?.supplier_name ??
        fallbackSupplier?.supplier_name ??
        request.incumbent_supplier ??
        "No recommendation yet",
      needsAttention:
        hasBlockingEscalation ||
        status === "pending_review" ||
        status === "escalated" ||
        recommendationStatus !== "proceed",
    }
  })
}

function isDashboardSnapshotFresh(
  snapshot: DashboardSnapshot,
  nowMs: number,
): boolean {
  return nowMs - snapshot.cachedAtMs < DASHBOARD_CACHE_TTL_MS
}

function fallbackReasonFromError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  return "Unable to refresh dashboard data from backend."
}

function toDashboardPageData(
  snapshot: DashboardSnapshot,
  mode: "fresh" | "stale",
  reason?: string,
): DashboardPageData {
  return {
    metrics: snapshot.metrics,
    cases: snapshot.cases,
    dataState: {
      mode,
      asOf: snapshot.asOf,
      ...(reason ? { reason } : {}),
    },
  }
}

async function refreshDashboardSnapshot(): Promise<DashboardSnapshot> {
  const rawData = await fetchDashboardRawData()
  const snapshot: DashboardSnapshot = {
    metrics: buildDashboardMetricsFromData(rawData),
    cases: buildCaseListFromData(rawData),
    asOf: new Date().toISOString(),
    cachedAtMs: Date.now(),
  }
  dashboardSnapshot = snapshot

  return snapshot
}

async function loadDashboardSnapshotWithDeduping(): Promise<DashboardSnapshot> {
  if (!dashboardSnapshotPromise) {
    dashboardSnapshotPromise = refreshDashboardSnapshot()
      .finally(() => {
        dashboardSnapshotPromise = null
      })
  }

  return await dashboardSnapshotPromise
}

function toAuditFeedEvent(
  award: HistoricalAward,
  titleByRequestId: Map<string, string>,
): AuditFeedEvent {
  const kind = award.escalation_required
    ? "escalation"
    : award.policy_compliant
      ? "policy"
      : "audit"

  return {
    id: award.award_id,
    timestamp: award.award_date,
    kind,
    title: `${award.supplier_name} ranked #${award.award_rank}`,
    description: award.decision_rationale,
    caseId: award.request_id,
    caseTitle: titleByRequestId.get(award.request_id) ?? "Sourcing request",
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

export async function getCaseDetailByRunId(
  runId: string,
): Promise<{ caseDetail: CaseDetail; runId: string } | null> {
  let evalDetail: EvaluationDetailApi
  try {
    evalDetail = await fetchJson<EvaluationDetailApi>(
      `/api/rule-versions/evaluations/${runId}`,
    )
  } catch (error) {
    if (error instanceof BackendApiError && error.status === 404) {
      return null
    }
    throw error
  }
  const requestId = evalDetail.request_id
  const caseDetail = await getCaseDetail(requestId)
  if (!caseDetail) return null
  return { caseDetail, runId }
}

export async function getCaseDetail(caseId: string): Promise<CaseDetail | null> {
  let detail: RequestDetail
  try {
    detail = await fetchJson<RequestDetail>(`/api/requests/${caseId}`)
  } catch (error) {
    if (error instanceof BackendApiError && error.status === 404) {
      return null
    }
    throw error
  }

  const [overview, awards, escalationRows, evaluationRunsRaw] = await Promise.all([
    fetchJson<RequestOverview>(`/api/analytics/request-overview/${caseId}`),
    fetchJson<HistoricalAward[]>(`/api/awards/by-request/${caseId}`),
    fetchEscalationRowsByRequest(caseId),
    fetchJson<EvaluationDetailApi[]>(`/api/rule-versions/evaluations/by-request/${caseId}`)
      .catch(() => []),
  ])

  const pricingBySupplier = new Map(
    overview.pricing.map((entry) => [entry.supplier_id, entry]),
  )

  const shortlist = overview.compliant_suppliers
    .map((supplier) => {
      const pricing = pricingBySupplier.get(supplier.supplier_id)
      if (!pricing) return null

      return {
        supplierId: supplier.supplier_id,
        supplierName: supplier.supplier_name,
        preferred: supplier.preferred_supplier,
        incumbent: supplier.supplier_name === detail.incumbent_supplier,
        pricingTierApplied: pricing.pricing_id,
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
        recommendationNote:
          "Eligible supplier after policy and region checks.",
      }
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null)
    .sort((a, b) => a.totalPrice - b.totalPrice)
    .map((entry, index) => ({ ...entry, rank: index + 1 }))

  const shortlistIds = new Set(shortlist.map((entry) => entry.supplierId))
  const excludedSuppliers = awards
    .filter((entry) => !shortlistIds.has(entry.supplier_id) && !entry.awarded)
    .map((entry) => ({
      supplierId: entry.supplier_id,
      supplierName: entry.supplier_name,
      reason: entry.decision_rationale,
      hardExclusion: !entry.policy_compliant || entry.escalation_required,
    }))

  const hasBlockingValidation = (detail.budget_amount ?? null) === null || (detail.quantity ?? null) === null

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

  const hasBlockingEscalation = escalations.some(
    (entry) => entry.blocking && entry.status !== "resolved",
  )
  const hasEscalation = escalations.some((entry) => entry.status !== "resolved")
  const status = normalizeStatus(detail.status)
  const recommendationStatus = recommendationStatusFrom(
    hasBlockingValidation || hasBlockingEscalation || shortlist.length === 0,
    hasEscalation,
    status,
  )

  const topSupplier = shortlist[0]
  const winner = awards.find((entry) => entry.awarded && entry.award_rank === 1)

  const policyCards = [
    ...overview.applicable_rules.category_rules.map((rule) => ({
      title: "Category Policy",
      ruleId: rule.rule_id,
      status: "informative" as const,
      summary: rule.rule_text,
      detail: [{ label: "Rule Type", value: rule.rule_type }],
    })),
    ...overview.applicable_rules.geography_rules.map((rule) => ({
      title: "Geography Policy",
      ruleId: rule.rule_id,
      status: "informative" as const,
      summary: rule.rule_text,
      detail: [
        { label: "Country", value: rule.country ?? "Regional" },
        { label: "Region", value: rule.region ?? "N/A" },
      ],
    })),
  ]

  const timeline = [
    {
      id: `${caseId}-source`,
      timestamp: detail.created_at,
      title: "Request ingested",
      description: "Procurement request persisted in organisational data layer.",
      kind: "source" as const,
    },
    {
      id: `${caseId}-policy`,
      timestamp: detail.created_at,
      title: "Policy and geography rules applied",
      description: `${policyCards.length} relevant rules evaluated for this context.`,
      kind: "policy" as const,
    },
    {
      id: `${caseId}-suppliers`,
      timestamp: detail.created_at,
      title: "Supplier shortlist generated",
      description: `${shortlist.length} compliant suppliers with pricing matched.`,
      kind: "supplier" as const,
    },
    ...escalations.map((entry) => ({
      id: `${entry.escalationId}-timeline`,
      timestamp:
        escalationRows.find((row) => row.escalationId === entry.escalationId)
          ?.createdAt ?? detail.created_at,
      title: `Escalation opened (${entry.rule})`,
      description: entry.trigger,
      kind: "escalation" as const,
    })),
    ...evaluationRunsRaw.map((run, idx) => ({
      id: run.run_id,
      timestamp: run.started_at,
      title: `Evaluation run ${idx + 1}`,
      description: `Decision snapshot from ${new Date(run.started_at).toLocaleString()}. Click to view full details.`,
      kind: "evaluation_run" as const,
      runId: run.run_id,
      favorite: run.favorite ?? false,
    })),
  ]

  const approvalTier = overview.approval_tier?.threshold_id ?? "Threshold unavailable"
  const quotesRequired = overview.approval_tier?.min_supplier_quotes ?? 0
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

  const validationIssues = [
    ...(detail.budget_amount === null
      ? [
          {
            issueId: "VAL-BUDGET-MISSING",
            severity: "high" as const,
            type: "missing_info",
            description: "No explicit budget amount provided in request data.",
            actionRequired: "Requester must provide budget to proceed autonomously.",
            blocking: true,
          },
        ]
      : []),
    ...(detail.quantity === null
      ? [
          {
            issueId: "VAL-QUANTITY-MISSING",
            severity: "high" as const,
            type: "missing_info",
            description: "Quantity is missing, so pricing tier cannot be validated robustly.",
            actionRequired: "Requester must confirm quantity for final supplier ranking.",
            blocking: true,
          },
        ]
      : []),
    ...(shortlist.length === 0
      ? [
          {
            issueId: "VAL-NO-COMPLIANT-SUPPLIER",
            severity: "critical" as const,
            type: "restricted",
            description: "No compliant supplier with valid pricing could be shortlisted.",
            actionRequired: "Escalate to sourcing manager for exception handling.",
            blocking: true,
          },
        ]
      : []),
  ]

  const evaluationRuns = evaluationRunsRaw.map(mapEvaluationRunDetail)

  return {
    id: caseId,
    title: detail.title,
    outcomeLabel:
      recommendationStatus === "proceed"
        ? "Proceed"
        : recommendationStatus === "proceed_with_conditions"
          ? "Proceed with conditions"
          : "Cannot proceed",
    rawRequest: {
      requestId: detail.request_id,
      createdAt: detail.created_at,
      requestChannel:
        detail.request_channel === "teams" || detail.request_channel === "email"
          ? detail.request_channel
          : "portal",
      requestLanguage: detail.request_language,
      businessUnit: detail.business_unit,
      country: detail.country,
      site: detail.site,
      requesterRole: detail.requester_role ?? "Not specified",
      submittedForId: detail.submitted_for_id,
      status,
      scenarioTags: normalizeTags(detail.scenario_tags.map((entry) => entry.tag)),
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
        recommendationStatus === "proceed"
          ? "Supplier shortlist satisfies the current policy checks."
          : "Case requires additional human validation before final award.",
      recommendedSupplier: winner?.supplier_name ?? topSupplier?.supplierName ?? null,
      preferredSupplierIfResolved:
        overview.compliant_suppliers.find((entry) => entry.preferred_supplier)
          ?.supplier_name ?? null,
      rationale:
        winner?.decision_rationale ??
        topSupplier?.recommendationNote ??
        "No compliant supplier meets all constraints yet.",
      totalPrice: winner ? toNumber(winner.total_value) : topSupplier?.totalPrice ?? null,
      minimumBudgetRequired: topSupplier?.totalPrice ?? null,
      currency: detail.currency,
      approvalTier,
      quotesRequired,
      complianceStatus:
        recommendationStatus === "cannot_proceed"
          ? "Blocked"
          : recommendationStatus === "proceed_with_conditions"
            ? "Conditional"
            : "Compliant",
    },
    interpretedRequirements,
    validationIssues,
    policyCards,
    supplierShortlist: shortlist,
    excludedSuppliers,
    evaluationRuns,
    escalations,
    auditTrail: {
      policiesChecked: policyCards.map((entry) => entry.ruleId),
      supplierIdsEvaluated: overview.compliant_suppliers.map((entry) => entry.supplier_id),
      pricingTiersApplied:
        overview.pricing.map((entry) => entry.pricing_id).join(", ") || "None",
      dataSourcesUsed: [
        "requests",
        "analytics.request-overview",
        "awards",
        "categories",
      ],
      historicalAwardsConsulted: awards.length > 0,
      historicalAwardNote:
        awards.length > 0
          ? `${awards.length} historical award rows referenced.`
          : "No historical awards for this request.",
      reasoningTrace: [
        "Parse and validate request fields (budget, quantity, delivery scope).",
        "Apply category and geography policy constraints.",
        "Build compliant supplier shortlist and price by tier.",
        "Determine approval tier and escalation requirements.",
      ],
      timeline: timeline.sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      ),
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
    lastUpdated: new Date().toISOString(),
  }
}

export async function getEscalationQueue(): Promise<QueueEscalationItem[]> {
  const escalationRows = await fetchEscalationQueueRows()
  return escalationRows.sort(
    (a, b) =>
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  )
}

export async function getAuditFeed(): Promise<AuditFeedEvent[]> {
  const [requests, awards] = await Promise.all([getAllRequests(), getAllAwards()])
  const titleByRequestId = new Map(
    requests.map((entry) => [entry.request_id, entry.title]),
  )

  return awards
    .map((award) => toAuditFeedEvent(award, titleByRequestId))
    .sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    )
}

export async function getAuditOverview(): Promise<{
  summary: Array<{ label: string; value: string; helper: string }>
}> {
  const [requests, awards, escalationRows] = await Promise.all([
    getAllRequests(),
    getAllAwards(),
    fetchEscalationQueueRows(),
  ])
  const policyConflicts = awards.filter((entry) => !entry.policy_compliant)

  return {
    summary: [
      {
        label: "Cases With Audit Trace",
        value: requests.length.toString(),
        helper: "Requests represented in the backend dataset",
      },
      {
        label: "Award Decisions",
        value: awards.length.toString(),
        helper: "Historical supplier-evaluation rows available for audit",
      },
      {
        label: "Escalation Events",
        value: escalationRows.length.toString(),
        helper: "Deterministic escalation objects generated by current policy logic",
      },
      {
        label: "Policy Conflicts",
        value: policyConflicts.length.toString(),
        helper: "Audit entries with non-compliant outcomes",
      },
    ],
  }
}
