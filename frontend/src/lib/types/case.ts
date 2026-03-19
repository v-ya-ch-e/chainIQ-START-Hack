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

export type Severity = "critical" | "high" | "medium" | "low"

export type RequestChannel = "portal" | "teams" | "email"

export interface RawRequest {
  requestId: string
  createdAt: string
  requestChannel: RequestChannel
  requestLanguage: string
  businessUnit: string
  country: string
  site: string
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
  issueId: string
  severity: Severity
  type: string
  description: string
  actionRequired: string
  blocking: boolean
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
  preferred: boolean
  incumbent: boolean
  pricingTierApplied: string
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
  favorite: boolean
  supplierBreakdowns: SupplierRuleBreakdown[]
  /** Supplier shortlist from this run (from output_snapshot). Used when run is selected. */
  supplierShortlist?: SupplierRow[]
  /** Excluded suppliers from this run (from output_snapshot). */
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
  quotesRequired: number
  complianceStatus: string
}

export interface AuditTimelineEvent {
  id: string
  timestamp: string
  title: string
  description: string
  kind: "source" | "interpretation" | "policy" | "supplier" | "escalation" | "audit" | "evaluation_run"
  /** When kind is evaluation_run, links to /cases/eval/{runId} */
  runId?: string
  /** When kind is evaluation_run, whether this run is favorited */
  favorite?: boolean
}

export interface AuditFeedEvent extends AuditTimelineEvent {
  caseId: string
  caseTitle: string
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
  tone?: "default" | "success" | "warning" | "destructive" | "info"
  helper: string
}

export interface DashboardDataState {
  mode: "fresh" | "stale"
  asOf: string
  reason?: string
}

export interface DashboardPageData {
  metrics: DashboardMetric[]
  cases: CaseListItem[]
  dataState: DashboardDataState
}
