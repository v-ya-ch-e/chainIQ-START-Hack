export type CaseStatus =
  | "received"
  | "parsed"
  | "pending_review"
  | "evaluated"
  | "recommended"
  | "escalated"
  | "resolved"

export type RecommendationStatus =
  | "proceed"
  | "proceed_with_conditions"
  | "cannot_proceed"
  | "not_evaluated"

export type ScenarioTag =
  | "standard"
  | "threshold"
  | "lead_time"
  | "missing_info"
  | "contradictory"
  | "restricted"
  | "multilingual"
  | "capacity"
  | "multi_country"
  | string

export type Severity = "critical" | "high" | "medium" | "low"

export type RequestChannel = "portal" | "teams" | "email"

export interface RawRequest {
  requestId: string
  categoryId?: number
  createdAt: string
  requestChannel: RequestChannel
  requestLanguage: string
  businessUnit: string
  country: string
  site: string
  requesterId?: string
  requesterRole: string
  submittedForId: string
  status: CaseStatus
  scenarioTags: ScenarioTag[]
  categoryL1: string
  categoryL2: string
  title: string
  requestText: string
  currency: string
  budgetAmount: number | null
  quantity: number | null
  unitOfMeasure: string
  requiredByDate: string
  deliveryCountries: string[]
  dataResidencyConstraint: boolean
  esgRequirement: boolean
  preferredSupplierMentioned: string | null
  incumbentSupplier: string | null
  contractTypeRequested: string
  requesterInstruction?: string | null
}

export interface InterpretedRequirement {
  label: string
  value: string
  emphasis?: boolean
  inferred?: boolean
}

export interface ValidationIssue {
  issueKey: string
  issueId: string
  severity: Severity
  type: string
  description: string
  actionRequired: string
  blocking: boolean
  auditRowId: number
  runId: string | null
  timestamp: string
  stepName: string | null
  level: string
  source: string
  details: Record<string, unknown> | null
}

export interface PolicyCardData {
  title: string
  ruleId: string
  status: "satisfied" | "conflict" | "informative"
  summary: string
  detail: Array<{ label: string; value: string }>
}

export interface SupplierRow {
  rank: number
  supplierId: string
  supplierName: string
  countryHq?: string
  currency?: string
  preferred: boolean
  incumbent: boolean
  pricingTierApplied: string
  region?: string
  minQuantity?: number
  maxQuantity?: number
  moq?: number
  unitPrice: number
  totalPrice: number
  standardLeadTimeDays: number
  expeditedLeadTimeDays: number
  expeditedUnitPrice: number
  expeditedTotal: number
  qualityScore: number
  riskScore: number
  esgScore: number
  policyCompliant: boolean
  coversDeliveryCountry: boolean
  dataResidencySupported?: boolean
  recommendationNote: string
}

export type RuleCheckResult = "passed" | "failed" | "warned" | "skipped"

export interface SupplierRuleCheck {
  checkId: string
  ruleId: string
  versionId: string
  supplierId: string | null
  result: RuleCheckResult
  checkedAt: string
  skipped?: boolean | null
  skipReason?: string | null
  evidence?: Record<string, unknown> | null
}

export interface SupplierRuleBreakdown {
  supplierId: string
  supplierName: string | null
  excluded: boolean
  exclusionRuleId: string | null
  exclusionReason: string | null
  hardRuleChecks: SupplierRuleCheck[]
  policyChecks: SupplierRuleCheck[]
}

export interface EvaluationRunDetail {
  runId: string
  requestId: string
  status: string
  startedAt: string
  finishedAt: string | null
  supplierBreakdowns: SupplierRuleBreakdown[]
  supplierShortlist?: SupplierRow[]
  excludedSuppliersFromRun?: ExcludedSupplier[]
}

export interface ExcludedSupplier {
  supplierId: string
  supplierName: string
  reason: string
  hardExclusion: boolean
}

export interface EscalationItem {
  escalationId: string
  rule: string
  ruleLabel?: string
  trigger: string
  escalateTo: string
  blocking: boolean
  status: "open" | "resolved"
  nextAction: string
}

export interface RecommendationSummary {
  status: RecommendationStatus
  reason: string
  recommendedSupplier: string | null
  preferredSupplierIfResolved?: string | null
  rationale: string
  totalPrice?: number | null
  minimumBudgetRequired?: number | null
  currency: string
  approvalTier: string
  minAmount?: number | null
  maxAmount?: number | null
  managers?: string[]
  deviationApprovers?: string[]
  policyNote?: string | null
  quotesRequired: number
  complianceStatus: string
}

export interface AuditTimelineEvent {
  id: string
  timestamp: string
  title: string
  description: string
  kind: "source" | "interpretation" | "policy" | "supplier" | "escalation" | "audit"
  level?: string
  category?: string
  stepName?: string | null
  source?: string
  details?: Record<string, unknown> | null
}

export interface AuditFeedEvent extends AuditTimelineEvent {
  caseId: string
  caseTitle: string
}

export interface AuditSummaryMetric {
  label: string
  value: string
  helper: string
}

export interface AuditFeedMeta {
  mode: "fresh" | "degraded"
  source: "orgLogs" | "orgLogsFallback" | "none"
  isTruncated: boolean
  totalKnown: number
  fetchedCount: number
  asOf: string
  warning?: string
}

export interface AuditPageData {
  summary: AuditSummaryMetric[]
  feed: AuditFeedEvent[]
  feedMeta: AuditFeedMeta
}

export interface AuditTrail {
  policiesChecked: string[]
  supplierIdsEvaluated: string[]
  pricingTiersApplied: string
  dataSourcesUsed: string[]
  historicalAwardsConsulted: boolean
  historicalAwardNote: string
  reasoningTrace: string[]
  timeline: AuditTimelineEvent[]
}

export interface HistoricalPrecedent {
  title: string
  description: string
  metrics: Array<{ label: string; value: string }>
}

export interface CaseDetail {
  id: string
  title: string
  outcomeLabel: string
  rawRequest: RawRequest
  recommendation: RecommendationSummary
  interpretedRequirements: InterpretedRequirement[]
  validationIssues: ValidationIssue[]
  policyCards: PolicyCardData[]
  supplierShortlist: SupplierRow[]
  excludedSuppliers: ExcludedSupplier[]
  evaluationRuns: EvaluationRunDetail[]
  escalations: EscalationItem[]
  auditTrail: AuditTrail
  historicalPrecedent?: HistoricalPrecedent
  lastUpdated: string
}

export interface CaseListItem {
  requestId: string
  title: string
  category: string
  businessUnit: string
  countryLabel: string
  budgetAmount: number | null
  currency: string
  requiredByDate: string
  status: CaseStatus
  scenarioTags: ScenarioTag[]
  recommendationStatus: RecommendationStatus
  escalationStatus: "none" | "advisory" | "blocking"
  lastUpdated: string
  supplierLabel: string
  needsAttention: boolean
}

export interface QueueEscalationItem {
  escalationId: string
  caseId: string
  title: string
  category: string
  businessUnit: string
  country: string
  ruleId: string
  ruleLabel: string
  escalateTo: string
  blocking: boolean
  status: "open" | "resolved"
  createdAt: string
  lastUpdated: string
  trigger: string
  recommendationStatus: RecommendationStatus
}

export interface DashboardMetric {
  label: string
  value: number
  valueLabel?: string
  tone?: "default" | "success" | "warning" | "destructive" | "info"
  helper: string
}

export interface DashboardDataState {
  mode: "fresh" | "stale"
  asOf: string
  reason?: string
}

export interface DashboardFilterOptions {
  statuses: CaseStatus[]
  categories: string[]
  countries: string[]
}

export interface DashboardStatusInsight {
  status: CaseStatus
  label: string
  count: number
}

export interface DashboardSpendByCategoryInsight {
  category: string
  totalSpend: number
  awardCount: number
}

export interface DashboardInsights {
  statusBreakdown: DashboardStatusInsight[]
  spendByCategory: DashboardSpendByCategoryInsight[]
  filterOptions: DashboardFilterOptions
}

export interface DashboardPageData {
  metrics: DashboardMetric[]
  cases: CaseListItem[]
  dataState: DashboardDataState
  insights: DashboardInsights
}

export type IntakeSourceType = "paste" | "upload" | "manual"

export type IntakeFlowStep = "input" | "processing" | "complete" | "review" | "created"

export type IntakeFieldStatus =
  | "confident"
  | "inferred"
  | "missing"
  | "needs_review"

export interface IntakeFieldMeta {
  status: IntakeFieldStatus
  confidence: number
  reason?: string
}

export interface CaseIntakeInput {
  sourceType: IntakeSourceType
  sourceText: string
  note?: string
  requestChannel?: RequestChannel
  fileNames?: string[]
}

export interface CategoryOption {
  id: number
  categoryL1: string
  categoryL2: string
}

export interface CaseDraftPayload {
  requestId?: string
  createdAt?: string
  title: string
  requestText: string
  requestChannel: RequestChannel
  requestLanguage: string
  businessUnit: string
  country: string
  site: string
  requesterId: string
  requesterRole: string
  submittedForId: string
  categoryId: number | null
  quantity: number | null
  unitOfMeasure: string
  currency: string
  budgetAmount: number | null
  requiredByDate: string
  deliveryCountries: string[]
  preferredSupplierMentioned: string | null
  incumbentSupplier: string | null
  contractTypeRequested: string
  dataResidencyConstraint: boolean
  esgRequirement: boolean
  requesterInstruction: string | null
  scenarioTags: ScenarioTag[]
  status: string
}

export interface ExtractionWarning {
  code: string
  severity: Severity
  message: string
}

export interface ExtractionResult {
  draft: CaseDraftPayload
  fieldStatus: Partial<Record<keyof CaseDraftPayload, IntakeFieldMeta>>
  missingRequired: Array<keyof CaseDraftPayload>
  warnings: ExtractionWarning[]
  extractionStrength: "strong" | "partial" | "low"
  fallbackUsed: boolean
}

export type CreateCasePayload = CaseDraftPayload
