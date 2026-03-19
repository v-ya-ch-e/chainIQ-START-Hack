import {
  ApiError,
  buildQuery,
  fetchAllPages,
  requestJson,
  requestNoContent,
} from "@/lib/api/http"
import type {
  ApplicableRulesParams,
  ApplicableRulesOut,
  ApprovalThresholdOut,
  ApprovalTierOut,
  AuditLogBatchCreate,
  AuditLogCreate,
  AuditLogListOut,
  AuditLogListParams,
  AuditLogOut,
  AuditLogSummaryOut,
  AwardListParams,
  BatchProcessRequest,
  BatchResponse,
  CategoryCreate,
  CategoryOut,
  CategoryRuleOut,
  CategoryUpdate,
  CompliantSupplierOut,
  CompliantSupplierParams,
  EscalationQueueItemOut,
  EscalationRuleOut,
  GeographyRuleOut,
  HistoricalAwardListOut,
  HistoricalAwardOut,
  ParseResponse,
  ParseTextRequest,
  PipelineLogEntryCreate,
  PipelineLogEntryOut,
  PipelineLogEntryUpdate,
  PipelineRunCreate,
  PipelineRunDetailOut,
  PipelineRunListOut,
  PipelineRunOut,
  PipelineRunUpdate,
  PreferredCheckOut,
  PreferredCheckParams,
  PreferredSupplierPolicyOut,
  PricingLookupOut,
  PricingLookupParams,
  PricingTierOut,
  ProcessRequest,
  RequestCreate,
  RequestDetailOut,
  RequestListOut,
  RequestListParams,
  RequestOut,
  RequestOverviewOut,
  RequestUpdate,
  RestrictedCheckParams,
  RestrictedSupplierPolicyOut,
  RestrictionCheckOut,
  RunListParams,
  SpendByCategoryOut,
  SpendBySupplierOut,
  StepRequest,
  SupplierCategoryOut,
  SupplierCreate,
  SupplierDetailOut,
  SupplierListParams,
  SupplierOut,
  SupplierPricingParams,
  SupplierServiceRegionOut,
  SupplierUpdate,
  SupplierWinRateOut,
} from "@/lib/api/types"

function jsonBody(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  }
}

function jsonPatch(body: unknown): RequestInit {
  return {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  }
}

function jsonPut(body: unknown): RequestInit {
  return {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  }
}

export const chainIqApi = {
  parse: {
    parseText(body: ParseTextRequest) {
      return requestJson<ParseResponse>("org", "/api/parse/text", jsonBody(body))
    },
    parseFile(file: File | Blob, filename = "upload.bin") {
      const formData = new FormData()
      formData.append("file", file, filename)

      return requestJson<ParseResponse>("org", "/api/parse/file", {
        method: "POST",
        body: formData,
      })
    },
  },

  requests: {
    list(params?: RequestListParams) {
      return requestJson<RequestListOut>(
        "org",
        `/api/requests/${buildQuery(params)}`,
      )
    },
    listAll(limit = 200) {
      return fetchAllPages(async (skip, pageLimit) => {
        return chainIqApi.requests.list({ skip, limit: pageLimit })
      }, limit)
    },
    get(requestId: string) {
      return requestJson<RequestDetailOut>("org", `/api/requests/${requestId}`)
    },
    create(body: RequestCreate) {
      return requestJson<RequestOut>("org", "/api/requests/", jsonBody(body))
    },
    update(requestId: string, body: RequestUpdate) {
      return requestJson<RequestOut>(
        "org",
        `/api/requests/${requestId}`,
        jsonPut(body),
      )
    },
    remove(requestId: string) {
      return requestNoContent("org", `/api/requests/${requestId}`, {
        method: "DELETE",
      })
    },
  },

  categories: {
    list() {
      return requestJson<CategoryOut[]>("org", "/api/categories/")
    },
    get(categoryId: number) {
      return requestJson<CategoryOut>("org", `/api/categories/${categoryId}`)
    },
    create(body: CategoryCreate) {
      return requestJson<CategoryOut>("org", "/api/categories/", jsonBody(body))
    },
    update(categoryId: number, body: CategoryUpdate) {
      return requestJson<CategoryOut>(
        "org",
        `/api/categories/${categoryId}`,
        jsonPut(body),
      )
    },
    remove(categoryId: number) {
      return requestNoContent("org", `/api/categories/${categoryId}`, {
        method: "DELETE",
      })
    },
  },

  suppliers: {
    list(params?: SupplierListParams) {
      return requestJson<SupplierOut[]>(
        "org",
        `/api/suppliers/${buildQuery(params)}`,
      )
    },
    get(supplierId: string) {
      return requestJson<SupplierDetailOut>("org", `/api/suppliers/${supplierId}`)
    },
    create(body: SupplierCreate) {
      return requestJson<SupplierOut>("org", "/api/suppliers/", jsonBody(body))
    },
    update(supplierId: string, body: SupplierUpdate) {
      return requestJson<SupplierOut>(
        "org",
        `/api/suppliers/${supplierId}`,
        jsonPut(body),
      )
    },
    remove(supplierId: string) {
      return requestNoContent("org", `/api/suppliers/${supplierId}`, {
        method: "DELETE",
      })
    },
    categories(supplierId: string) {
      return requestJson<SupplierCategoryOut[]>(
        "org",
        `/api/suppliers/${supplierId}/categories`,
      )
    },
    regions(supplierId: string) {
      return requestJson<SupplierServiceRegionOut[]>(
        "org",
        `/api/suppliers/${supplierId}/regions`,
      )
    },
    pricing(supplierId: string, params?: SupplierPricingParams) {
      return requestJson<PricingTierOut[]>(
        "org",
        `/api/suppliers/${supplierId}/pricing${buildQuery(params)}`,
      )
    },
  },

  awards: {
    list(params?: AwardListParams) {
      return requestJson<HistoricalAwardListOut>(
        "org",
        `/api/awards/${buildQuery(params)}`,
      )
    },
    listAll(limit = 200) {
      return fetchAllPages(async (skip, pageLimit) => {
        return chainIqApi.awards.list({ skip, limit: pageLimit })
      }, limit)
    },
    byRequest(requestId: string) {
      return requestJson<HistoricalAwardOut[]>(
        "org",
        `/api/awards/by-request/${requestId}`,
      )
    },
    get(awardId: string) {
      return requestJson<HistoricalAwardOut>("org", `/api/awards/${awardId}`)
    },
  },

  escalations: {
    queue() {
      return requestJson<EscalationQueueItemOut[]>("org", "/api/escalations/queue")
    },
    byRequest(requestId: string) {
      return requestJson<EscalationQueueItemOut[]>(
        "org",
        `/api/escalations/by-request/${requestId}`,
      )
    },
  },

  policies: {
    approvalThresholds(currency?: string) {
      return requestJson<ApprovalThresholdOut[]>(
        "org",
        `/api/policies/approval-thresholds${buildQuery(
          currency ? { currency } : undefined,
        )}`,
      )
    },
    approvalThreshold(thresholdId: string) {
      return requestJson<ApprovalThresholdOut>(
        "org",
        `/api/policies/approval-thresholds/${thresholdId}`,
      )
    },
    preferredSuppliers(params?: { supplier_id?: string; category_l1?: string }) {
      return requestJson<PreferredSupplierPolicyOut[]>(
        "org",
        `/api/policies/preferred-suppliers${buildQuery(params)}`,
      )
    },
    preferredSupplier(policyId: number) {
      return requestJson<PreferredSupplierPolicyOut>(
        "org",
        `/api/policies/preferred-suppliers/${policyId}`,
      )
    },
    restrictedSuppliers(params?: { supplier_id?: string }) {
      return requestJson<RestrictedSupplierPolicyOut[]>(
        "org",
        `/api/policies/restricted-suppliers${buildQuery(params)}`,
      )
    },
    restrictedSupplier(policyId: number) {
      return requestJson<RestrictedSupplierPolicyOut>(
        "org",
        `/api/policies/restricted-suppliers/${policyId}`,
      )
    },
  },

  rules: {
    category(categoryId?: number) {
      return requestJson<CategoryRuleOut[]>(
        "org",
        `/api/rules/category${buildQuery(
          categoryId ? { category_id: categoryId } : undefined,
        )}`,
      )
    },
    categoryById(ruleId: string) {
      return requestJson<CategoryRuleOut>("org", `/api/rules/category/${ruleId}`)
    },
    geography(country?: string) {
      return requestJson<GeographyRuleOut[]>(
        "org",
        `/api/rules/geography${buildQuery(country ? { country } : undefined)}`,
      )
    },
    geographyById(ruleId: string) {
      return requestJson<GeographyRuleOut>("org", `/api/rules/geography/${ruleId}`)
    },
    escalation() {
      return requestJson<EscalationRuleOut[]>("org", "/api/rules/escalation")
    },
    escalationById(ruleId: string) {
      return requestJson<EscalationRuleOut>(
        "org",
        `/api/rules/escalation/${ruleId}`,
      )
    },
  },

  analytics: {
    compliantSuppliers(params: CompliantSupplierParams) {
      return requestJson<CompliantSupplierOut[]>(
        "org",
        `/api/analytics/compliant-suppliers${buildQuery(params)}`,
      )
    },
    pricingLookup(params: PricingLookupParams) {
      return requestJson<PricingLookupOut[]>(
        "org",
        `/api/analytics/pricing-lookup${buildQuery(params)}`,
      )
    },
    approvalTier(currency: string, amount: number | string) {
      return requestJson<ApprovalTierOut>(
        "org",
        `/api/analytics/approval-tier${buildQuery({ currency, amount })}`,
      )
    },
    checkRestricted(params: RestrictedCheckParams) {
      return requestJson<RestrictionCheckOut>(
        "org",
        `/api/analytics/check-restricted${buildQuery(params)}`,
      )
    },
    checkPreferred(params: PreferredCheckParams) {
      return requestJson<PreferredCheckOut>(
        "org",
        `/api/analytics/check-preferred${buildQuery(params)}`,
      )
    },
    applicableRules(params: ApplicableRulesParams) {
      return requestJson<ApplicableRulesOut>(
        "org",
        `/api/analytics/applicable-rules${buildQuery(params)}`,
      )
    },
    requestOverview(requestId: string) {
      return requestJson<RequestOverviewOut>(
        "org",
        `/api/analytics/request-overview/${requestId}`,
      )
    },
    spendByCategory() {
      return requestJson<SpendByCategoryOut[]>("org", "/api/analytics/spend-by-category")
    },
    spendBySupplier() {
      return requestJson<SpendBySupplierOut[]>("org", "/api/analytics/spend-by-supplier")
    },
    supplierWinRates() {
      return requestJson<SupplierWinRateOut[]>(
        "org",
        "/api/analytics/supplier-win-rates",
      )
    },
  },

  orgLogs: {
    runs: {
      create(body: PipelineRunCreate) {
        return requestJson<PipelineRunOut>("org", "/api/logs/runs", jsonBody(body))
      },
      list(params?: RunListParams) {
        return requestJson<PipelineRunListOut>(
          "org",
          `/api/logs/runs${buildQuery(params)}`,
        )
      },
      update(runId: string, body: PipelineRunUpdate) {
        return requestJson<PipelineRunOut>(
          "org",
          `/api/logs/runs/${runId}`,
          jsonPatch(body),
        )
      },
      get(runId: string) {
        return requestJson<PipelineRunDetailOut>("org", `/api/logs/runs/${runId}`)
      },
      byRequest(requestId: string) {
        return requestJson<PipelineRunDetailOut[]>(
          "org",
          `/api/logs/by-request/${requestId}`,
        )
      },
    },
    entries: {
      create(body: PipelineLogEntryCreate) {
        return requestJson<PipelineLogEntryOut>(
          "org",
          "/api/logs/entries",
          jsonBody(body),
        )
      },
      update(entryId: number, body: PipelineLogEntryUpdate) {
        return requestJson<PipelineLogEntryOut>(
          "org",
          `/api/logs/entries/${entryId}`,
          jsonPatch(body),
        )
      },
    },
    audit: {
      create(body: AuditLogCreate) {
        return requestJson<AuditLogOut>("org", "/api/logs/audit", jsonBody(body))
      },
      list(params?: AuditLogListParams) {
        return requestJson<AuditLogListOut>(
          "org",
          `/api/logs/audit${buildQuery(params)}`,
        )
      },
      createBatch(body: AuditLogBatchCreate) {
        return requestJson<AuditLogOut[]>(
          "org",
          "/api/logs/audit/batch",
          jsonBody(body),
        )
      },
      byRequest(requestId: string, params?: Omit<AuditLogListParams, "request_id">) {
        return requestJson<AuditLogListOut>(
          "org",
          `/api/logs/audit/by-request/${requestId}${buildQuery(params)}`,
        )
      },
      summary(requestId: string) {
        return requestJson<AuditLogSummaryOut>(
          "org",
          `/api/logs/audit/summary/${requestId}`,
        )
      },
    },
  },

  pipeline: {
    process(body: ProcessRequest) {
      return requestJson<Record<string, unknown>>(
        "logical",
        "/api/pipeline/process",
        jsonBody(body),
      )
    },
    processBatch(body: BatchProcessRequest) {
      return requestJson<BatchResponse>(
        "logical",
        "/api/pipeline/process-batch",
        jsonBody(body),
      )
    },
    status(requestId: string) {
      return requestJson<Record<string, unknown>>(
        "logical",
        `/api/pipeline/status/${requestId}`,
      )
    },
    result(requestId: string) {
      return requestJson<Record<string, unknown>>(
        "logical",
        `/api/pipeline/result/${requestId}`,
      )
    },
    runs(params?: RunListParams) {
      return requestJson<Record<string, unknown>>(
        "logical",
        `/api/pipeline/runs${buildQuery(params)}`,
      )
    },
    run(runId: string) {
      return requestJson<Record<string, unknown>>(
        "logical",
        `/api/pipeline/runs/${runId}`,
      )
    },
    audit(requestId: string, params?: Omit<AuditLogListParams, "request_id">) {
      return requestJson<AuditLogListOut>(
        "logical",
        `/api/pipeline/audit/${requestId}${buildQuery(params)}`,
      )
    },
    auditSummary(requestId: string) {
      return requestJson<AuditLogSummaryOut>(
        "logical",
        `/api/pipeline/audit/${requestId}/summary`,
      )
    },
    steps: {
      fetch(body: StepRequest) {
        return requestJson<Record<string, unknown>>(
          "logical",
          "/api/pipeline/steps/fetch",
          jsonBody(body),
        )
      },
      validate(body: StepRequest) {
        return requestJson<Record<string, unknown>>(
          "logical",
          "/api/pipeline/steps/validate",
          jsonBody(body),
        )
      },
      filter(body: StepRequest) {
        return requestJson<Record<string, unknown>>(
          "logical",
          "/api/pipeline/steps/filter",
          jsonBody(body),
        )
      },
      comply(body: StepRequest) {
        return requestJson<Record<string, unknown>>(
          "logical",
          "/api/pipeline/steps/comply",
          jsonBody(body),
        )
      },
      rank(body: StepRequest) {
        return requestJson<Record<string, unknown>>(
          "logical",
          "/api/pipeline/steps/rank",
          jsonBody(body),
        )
      },
      escalate(body: StepRequest) {
        return requestJson<Record<string, unknown>>(
          "logical",
          "/api/pipeline/steps/escalate",
          jsonBody(body),
        )
      },
    },
  },

  health: {
    org() {
      return requestJson<Record<string, unknown>>("org", "/health")
    },
    logical() {
      return requestJson<Record<string, unknown>>("logical", "/health")
    },
  },
}

export type ChainIqApi = typeof chainIqApi

export { ApiError }
