import { chainIqApi } from "@/lib/api/client"
import type {
  AuditFeedEvent,
  CaseDetail,
  CaseListItem,
  CaseStatus,
  DashboardMetric,
  DashboardPageData,
  QueueEscalationItem,
  RecommendationStatus,
  ScenarioTag,
  Severity,
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

let dashboardSnapshot: DashboardSnapshot | null = null
let dashboardSnapshotPromise: Promise<DashboardSnapshot> | null = null

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

async function buildDashboardMetricsFromData({
  requests,
  awards,
  escalationRows,
}: Pick<DashboardRawData, "requests" | "awards" | "escalationRows">): Promise<
  DashboardMetric[]
> {
  const [spendByCategory, spendBySupplier, supplierWinRates] = await Promise.all([
    chainIqApi.analytics.spendByCategory().catch(() => []),
    chainIqApi.analytics.spendBySupplier().catch(() => []),
    chainIqApi.analytics.supplierWinRates().catch(() => []),
  ])

  const blockingCases = new Set(
    escalationRows
      .filter((entry) => entry.blocking && entry.status !== "resolved")
      .map((entry) => entry.caseId),
  )

  const totalSpend = (spendByCategory as Array<{ total_spend?: string }>)
    .map((row) => toNumber(row.total_spend ?? null) ?? 0)
    .reduce((acc, value) => acc + value, 0)

  const topSupplier = (spendBySupplier as Array<{
    supplier_name?: string
    total_spend?: string
  }>)[0]
  const topWinRate = (supplierWinRates as Array<{ win_rate?: string }>)[0]

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
        : "No data",
      helper: topWinRate?.win_rate
        ? `Win rate ${(Number(topWinRate.win_rate) * 100).toFixed(1)}%`
        : "Supplier win-rate data unavailable",
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
  const metrics = await buildDashboardMetricsFromData(rawData)
  const snapshot: DashboardSnapshot = {
    metrics,
    cases: buildCaseListFromData(rawData),
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

  const [overview, awards, escalationRows, auditLogs, auditSummary] =
    await Promise.all([
      chainIqApi.analytics.requestOverview(caseId) as Promise<RequestOverview>,
      chainIqApi.awards.byRequest(caseId) as Promise<HistoricalAward[]>,
      fetchEscalationRowsByRequest(caseId),
      chainIqApi.orgLogs.audit
        .byRequest(caseId, { limit: 500 })
        .catch(async () =>
          (await chainIqApi.pipeline.audit(caseId, {
            limit: 500,
          })) as AuditListOut,
        ),
      chainIqApi.orgLogs.audit
        .summary(caseId)
        .catch(async () =>
          (await chainIqApi.pipeline.auditSummary(caseId)) as AuditSummaryOut,
        ),
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

  const shortlistIds = new Set(shortlist.map((entry) => entry.supplierId))
  const excludedSuppliers = awards
    .filter((entry) => !shortlistIds.has(entry.supplier_id) && !entry.awarded)
    .map((entry) => ({
      supplierId: entry.supplier_id,
      supplierName: entry.supplier_name,
      reason: entry.decision_rationale,
      hardExclusion: !entry.policy_compliant || entry.escalation_required,
    }))

  const escalationIssues = auditLogs.items
    .filter((entry) => entry.category === "escalation")
    .map((entry, index) => {
      const details = asRecord(entry.details)
      return {
        issueId: `ESC-${index + 1}`,
        severity: "critical" as Severity,
        type: "escalation",
        description: entry.message,
        actionRequired: `Escalate to ${(details?.escalate_to as string | undefined) ?? "assigned stakeholder"}.`,
        blocking: Boolean(details?.blocking ?? true),
      }
    })

  const validationIssues = [
    ...auditLogs.items
      .filter((entry) => entry.category === "validation")
      .map((entry, index) => {
        const details = asRecord(entry.details)
        const severity = details?.severity as string | undefined
        return {
          issueId:
            (details?.issue_type as string | undefined)?.toUpperCase() ??
            `VAL-${index + 1}`,
          severity: severityFrom(severity),
          type: entry.category,
          description: entry.message,
          actionRequired:
            (details?.action_required as string | undefined) ??
            "Review validation findings and update request input.",
          blocking: severity === "critical" || severity === "high",
        }
      }),
    ...escalationIssues,
  ]

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
  const recommendationStatus = recommendationStatusFrom(
    hasBlockingValidation || hasBlockingEscalation || shortlist.length === 0,
    hasEscalation,
    status,
  )

  const winner = awards.find((entry) => entry.awarded && entry.award_rank === 1)
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
      approvalTier: overview.approval_tier?.threshold_id ?? "Threshold unavailable",
      minAmount: toNumber(overview.approval_tier?.min_amount),
      maxAmount: toNumber(overview.approval_tier?.max_amount ?? null),
      managers: overview.approval_tier?.managers ?? [],
      deviationApprovers: overview.approval_tier?.deviation_approvers ?? [],
      policyNote: overview.approval_tier?.policy_note ?? null,
      quotesRequired: overview.approval_tier?.min_supplier_quotes ?? 0,
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
        auditLogs.items.length > 0
          ? auditLogs.items.slice(0, 8).map((entry) => entry.message)
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

export async function getAuditFeed(): Promise<AuditFeedEvent[]> {
  const [requests, audit] = await Promise.all([
    getAllRequests(),
    chainIqApi.orgLogs.audit.list({ limit: 500 }),
  ])
  const titleByRequestId = new Map(
    requests.map((entry) => [entry.request_id, entry.title]),
  )

  const typedAudit = audit as AuditListOut

  return typedAudit.items
    .map((entry) => mapAuditEvent(entry, titleByRequestId))
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}

export async function getAuditOverview(): Promise<{
  summary: Array<{ label: string; value: string; helper: string }>
}> {
  const [requests, escalationRows, audit] = await Promise.all([
    getAllRequests(),
    fetchEscalationQueueRows(),
    chainIqApi.orgLogs.audit.list({ limit: 500 }).catch(() => ({ items: [], total: 0 })),
  ])

  const typedAudit = audit as AuditListOut
  const policyConflicts = typedAudit.items.filter(
    (entry) => entry.category === "policy" && entry.level === "error",
  )

  return {
    summary: [
      {
        label: "Cases With Audit Trace",
        value: requests.length.toString(),
        helper: "Requests represented in the backend dataset",
      },
      {
        label: "Audit Entries",
        value: typedAudit.total.toString(),
        helper: "Structured pipeline events available for review",
      },
      {
        label: "Escalation Events",
        value: escalationRows.length.toString(),
        helper: "Deterministic escalation objects generated by policy logic",
      },
      {
        label: "Policy Conflicts",
        value: policyConflicts.length.toString(),
        helper: "Audit entries flagged as policy-level errors",
      },
    ],
  }
}
