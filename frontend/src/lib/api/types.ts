export type JsonPrimitive = string | number | boolean | null
export type JsonValue =
  | JsonPrimitive
  | { [key: string]: JsonValue }
  | JsonValue[]

export interface ParseTextRequest {
  text: string
}

export interface ParsedRequest {
  request_id: string | null
  created_at: string | null
  request_channel: string | null
  request_language: string | null
  business_unit: string | null
  country: string | null
  site: string | null
  requester_id: string | null
  requester_role: string | null
  submitted_for_id: string | null
  category_l1: string | null
  category_l2: string | null
  title: string | null
  request_text: string | null
  currency: string | null
  budget_amount: number | string | null
  quantity: number | string | null
  unit_of_measure: string | null
  required_by_date: string | null
  preferred_supplier_mentioned: string | null
  incumbent_supplier: string | null
  contract_type_requested: string | null
  delivery_countries: string[]
  data_residency_constraint: boolean
  esg_requirement: boolean
  status: string
  scenario_tags: string[]
  [key: string]: JsonValue
}

export interface ParseResponse {
  complete: boolean
  request: ParsedRequest
}

export interface CategoryOut {
  id: number
  category_l1: string
  category_l2: string
  category_description: string
  typical_unit: string
  pricing_model: string
}

export interface CategoryCreate {
  category_l1: string
  category_l2: string
  category_description: string
  typical_unit: string
  pricing_model: string
}

export interface CategoryUpdate {
  category_l1?: string | null
  category_l2?: string | null
  category_description?: string | null
  typical_unit?: string | null
  pricing_model?: string | null
}

export interface SupplierOut {
  supplier_id: string
  supplier_name: string
  country_hq: string
  currency: string
  contract_status: string
  capacity_per_month: number
}

export interface SupplierCategoryOut {
  id: number
  supplier_id: string
  category_id: number
  pricing_model: string
  quality_score: number
  risk_score: number
  esg_score: number
  preferred_supplier: boolean
  is_restricted: boolean
  restriction_reason: string | null
  data_residency_supported: boolean
  notes: string | null
}

export interface SupplierServiceRegionOut {
  supplier_id: string
  country_code: string
}

export interface SupplierDetailOut extends SupplierOut {
  categories: SupplierCategoryOut[]
  service_regions: SupplierServiceRegionOut[]
}

export interface PricingTierOut {
  pricing_id: string
  supplier_id: string
  category_id: number
  region: string
  currency: string
  pricing_model: string
  min_quantity: number
  max_quantity: number
  unit_price: string
  moq: number
  standard_lead_time_days: number
  expedited_lead_time_days: number
  expedited_unit_price: string
  valid_from: string
  valid_to: string
  notes: string | null
}

export interface SupplierCreate {
  supplier_id: string
  supplier_name: string
  country_hq: string
  currency: string
  contract_status: string
  capacity_per_month: number
}

export interface SupplierUpdate {
  supplier_name?: string | null
  country_hq?: string | null
  currency?: string | null
  contract_status?: string | null
  capacity_per_month?: number | null
}

export interface RequestDeliveryCountryOut {
  id: number
  country_code: string
}

export interface RequestScenarioTagOut {
  id: number
  tag: string
}

export interface RequestListItemOut {
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
  budget_amount: string | null
  quantity: string | null
  unit_of_measure: string
  required_by_date: string
  preferred_supplier_mentioned: string | null
  incumbent_supplier: string | null
  contract_type_requested: string
  data_residency_constraint: boolean
  esg_requirement: boolean
  status: string
  scenario_tags: string[]
}

export interface RequestListOut {
  items: RequestListItemOut[]
  total: number
  skip: number
  limit: number
}

export interface RequestOut {
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
  budget_amount: string | null
  quantity: string | null
  unit_of_measure: string
  required_by_date: string
  preferred_supplier_mentioned: string | null
  incumbent_supplier: string | null
  contract_type_requested: string
  data_residency_constraint: boolean
  esg_requirement: boolean
  status: string
}

export interface RequestDetailOut extends RequestOut {
  delivery_countries: RequestDeliveryCountryOut[]
  scenario_tags: RequestScenarioTagOut[]
  category_l1: string | null
  category_l2: string | null
}

export interface RequestCreate {
  request_id: string
  created_at: string
  request_channel: string
  request_language: string
  business_unit: string
  country: string
  site: string
  requester_id: string
  requester_role?: string | null
  submitted_for_id: string
  category_id: number
  title: string
  request_text: string
  currency: string
  budget_amount?: number | string | null
  quantity?: number | string | null
  unit_of_measure: string
  required_by_date: string
  preferred_supplier_mentioned?: string | null
  incumbent_supplier?: string | null
  contract_type_requested: string
  data_residency_constraint?: boolean
  esg_requirement?: boolean
  status?: string
  delivery_countries?: string[]
  scenario_tags?: string[]
}

export interface RequestUpdate {
  title?: string | null
  request_text?: string | null
  currency?: string | null
  budget_amount?: number | string | null
  quantity?: number | string | null
  unit_of_measure?: string | null
  required_by_date?: string | null
  preferred_supplier_mentioned?: string | null
  incumbent_supplier?: string | null
  contract_type_requested?: string | null
  data_residency_constraint?: boolean | null
  esg_requirement?: boolean | null
  status?: string | null
}

export interface HistoricalAwardOut {
  award_id: string
  request_id: string
  award_date: string
  category_id: number
  country: string
  business_unit: string
  supplier_id: string
  supplier_name: string
  total_value: string
  currency: string
  quantity: string
  required_by_date: string
  awarded: boolean
  award_rank: number
  decision_rationale: string
  policy_compliant: boolean
  preferred_supplier_used: boolean
  escalation_required: boolean
  escalated_to: string | null
  savings_pct: string
  lead_time_days: number
  risk_score_at_award: number
  notes: string | null
}

export interface HistoricalAwardListOut {
  items: HistoricalAwardOut[]
  total: number
  skip: number
  limit: number
}

export interface EscalationQueueItemOut {
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
  recommendation_status:
    | "proceed"
    | "proceed_with_conditions"
    | "cannot_proceed"
}

export interface ApprovalThresholdManagerOut {
  id: number
  managed_by: string
}

export interface ApprovalThresholdDeviationApproverOut {
  id: number
  approver: string
}

export interface ApprovalThresholdOut {
  threshold_id: string
  currency: string
  min_amount: string
  max_amount: string | null
  min_supplier_quotes: number
  policy_note: string | null
  managers: ApprovalThresholdManagerOut[]
  deviation_approvers: ApprovalThresholdDeviationApproverOut[]
}

export interface PreferredSupplierRegionScopeOut {
  id: number
  region: string
}

export interface PreferredSupplierPolicyOut {
  id: number
  supplier_id: string
  category_l1: string
  category_l2: string
  policy_note: string | null
  region_scopes: PreferredSupplierRegionScopeOut[]
}

export interface RestrictedSupplierScopeOut {
  id: number
  scope_value: string
}

export interface RestrictedSupplierPolicyOut {
  id: number
  supplier_id: string
  category_l1: string
  category_l2: string
  restriction_reason: string
  scopes: RestrictedSupplierScopeOut[]
}

export interface CategoryRuleOut {
  rule_id: string
  category_id: number
  rule_type: string
  rule_text: string
}

export interface GeographyRuleCountryOut {
  id: number
  country_code: string
}

export interface GeographyRuleAppliesToCategoryOut {
  id: number
  category_l1: string
  category_l2: string
}

export interface GeographyRuleOut {
  rule_id: string
  country: string | null
  region: string | null
  rule_type: string | null
  rule_text: string
  countries: GeographyRuleCountryOut[]
  applies_to_categories: GeographyRuleAppliesToCategoryOut[]
}

export interface EscalationRuleCurrencyOut {
  id: number
  currency: string
}

export interface EscalationRuleOut {
  rule_id: string
  trigger_condition: string
  action: string
  escalate_to: string
  currencies: EscalationRuleCurrencyOut[]
}

export interface CompliantSupplierOut {
  supplier_id: string
  supplier_name: string
  country_hq: string
  currency: string
  quality_score: number
  risk_score: number
  esg_score: number
  preferred_supplier: boolean
  data_residency_supported: boolean
}

export interface PricingLookupOut {
  pricing_id: string
  supplier_id: string
  supplier_name: string
  region: string
  currency: string
  min_quantity: number
  max_quantity: number
  unit_price: string
  expedited_unit_price: string
  total_price: string
  expedited_total_price: string
  standard_lead_time_days: number
  expedited_lead_time_days: number
  moq: number
}

export interface RestrictionCheckOut {
  supplier_id: string
  is_restricted: boolean
  restriction_reason: string | null
  scope_values: string[]
}

export interface PreferredCheckOut {
  supplier_id: string
  is_preferred: boolean
  policy_note: string | null
  region_scopes: string[]
}

export interface ApplicableRulesOut {
  category_rules: Record<string, JsonValue>[]
  geography_rules: Record<string, JsonValue>[]
}

export interface ApprovalTierOut {
  threshold_id: string
  currency: string
  min_amount: string
  max_amount: string | null
  min_supplier_quotes: number
  policy_note: string | null
  managers: string[]
  deviation_approvers: string[]
}

export interface RequestOverviewOut {
  request: Record<string, JsonValue>
  compliant_suppliers: CompliantSupplierOut[]
  pricing: PricingLookupOut[]
  applicable_rules: ApplicableRulesOut
  approval_tier: ApprovalTierOut | null
  historical_awards: Record<string, JsonValue>[]
}

export interface SpendByCategoryOut {
  category_l1: string
  category_l2: string
  total_spend: string
  award_count: number
  avg_savings_pct: string
}

export interface SpendBySupplierOut {
  supplier_id: string
  supplier_name: string
  total_spend: string
  award_count: number
  avg_savings_pct: string
}

export interface SupplierWinRateOut {
  supplier_id: string
  supplier_name: string
  total_evaluations: number
  wins: number
  win_rate: string
}

export interface PipelineRunCreate {
  run_id: string
  request_id: string
  started_at: string
}

export interface PipelineRunUpdate {
  status?: string | null
  completed_at?: string | null
  total_duration_ms?: number | null
  steps_completed?: number | null
  steps_failed?: number | null
  error_message?: string | null
}

export interface PipelineLogEntryCreate {
  run_id: string
  step_name: string
  step_order: number
  started_at: string
  input_summary?: JsonValue
}

export interface PipelineLogEntryUpdate {
  status?: string | null
  completed_at?: string | null
  duration_ms?: number | null
  output_summary?: JsonValue
  error_message?: string | null
  metadata_?: JsonValue
}

export interface PipelineLogEntryOut {
  id: number
  run_id: string
  step_name: string
  step_order: number
  status: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  input_summary: JsonValue
  output_summary: JsonValue
  error_message: string | null
  metadata_: JsonValue
}

export interface PipelineRunOut {
  id: number
  run_id: string
  request_id: string
  status: string
  started_at: string
  completed_at: string | null
  total_duration_ms: number | null
  steps_completed: number
  steps_failed: number
  error_message: string | null
}

export interface PipelineRunDetailOut extends PipelineRunOut {
  entries: PipelineLogEntryOut[]
}

export interface PipelineRunListOut {
  items: PipelineRunOut[]
  total: number
}

export interface AuditLogCreate {
  request_id: string
  run_id?: string | null
  timestamp: string
  level?: string
  category?: string
  step_name?: string | null
  message: string
  details?: JsonValue
  source?: string
}

export interface AuditLogBatchCreate {
  entries: AuditLogCreate[]
}

export interface AuditLogOut {
  id: number
  request_id: string
  run_id: string | null
  timestamp: string
  level: string
  category: string
  step_name: string | null
  message: string
  details: JsonValue
  source: string
}

export interface AuditLogListOut {
  items: AuditLogOut[]
  total: number
}

export interface LevelCount {
  level: string
  count: number
}

export interface CategoryCount {
  category: string
  count: number
}

export interface AuditLogSummaryOut {
  request_id: string
  total_entries: number
  by_level: LevelCount[]
  by_category: CategoryCount[]
  distinct_policies: string[]
  distinct_suppliers: string[]
  escalation_count: number
  first_event: string | null
  last_event: string | null
}

export interface ProcessRequest {
  request_id: string
}

export interface StepRequest {
  request_id: string
}

export interface BatchProcessRequest {
  request_ids: string[]
  concurrency?: number
}

export interface BatchResponse {
  batch_id: string
  queued: number
  concurrency: number
  message: string
}

export type RequestListParams = {
  skip?: number
  limit?: number
  country?: string
  category_id?: number
  status?: string
  currency?: string
  tag?: string
}

export type SupplierListParams = {
  country_hq?: string
  currency?: string
  category_l1?: string
}

export type SupplierPricingParams = {
  category_id?: number
  region?: string
}

export type AwardListParams = {
  skip?: number
  limit?: number
  request_id?: string
  supplier_id?: string
  awarded?: boolean
  policy_compliant?: boolean
}

export type AuditLogListParams = {
  request_id?: string
  level?: string
  category?: string
  run_id?: string
  step_name?: string
  skip?: number
  limit?: number
}

export type RunListParams = {
  request_id?: string
  status?: string
  skip?: number
  limit?: number
}

export type CompliantSupplierParams = {
  category_l1: string
  category_l2: string
  delivery_country: string
}

export type PricingLookupParams = {
  supplier_id: string
  category_l1: string
  category_l2: string
  region: string
  quantity: number | string
}

export type RestrictedCheckParams = {
  supplier_id: string
  category_l1: string
  category_l2: string
  delivery_country: string
}

export type PreferredCheckParams = {
  supplier_id: string
  category_l1: string
  category_l2: string
  region?: string
}

export type ApplicableRulesParams = {
  category_l1: string
  category_l2: string
  delivery_country: string
}
