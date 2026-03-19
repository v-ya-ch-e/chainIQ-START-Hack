"use client"

import { useMemo, useState } from "react"
import { Database, Search } from "lucide-react"

import { chainIqApi } from "@/lib/api/client"
import { SectionHeading } from "@/components/shared/section-heading"
import { JsonViewer } from "@/components/shared/json-viewer"
import {
  EmptyStateCard,
  ErrorStateCard,
  FallbackBanner,
} from "@/components/shared/state-cards"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

type JsonMap = Record<string, unknown>

interface ApiClientShape {
  requests: {
    list: (params?: JsonMap) => Promise<unknown>
    get: (requestId: string) => Promise<unknown>
    create: (payload: JsonMap) => Promise<unknown>
    update: (requestId: string, payload: JsonMap) => Promise<unknown>
    remove: (requestId: string) => Promise<void>
  }
  categories: {
    list: () => Promise<unknown>
    get: (categoryId: number) => Promise<unknown>
    create: (payload: JsonMap) => Promise<unknown>
    update: (categoryId: number, payload: JsonMap) => Promise<unknown>
    remove: (categoryId: number) => Promise<void>
  }
  suppliers: {
    list: (params?: JsonMap) => Promise<unknown>
    get: (supplierId: string) => Promise<unknown>
    create: (payload: JsonMap) => Promise<unknown>
    update: (supplierId: string, payload: JsonMap) => Promise<unknown>
    remove: (supplierId: string) => Promise<void>
    categories: (supplierId: string) => Promise<unknown>
    regions: (supplierId: string) => Promise<unknown>
    pricing: (supplierId: string, params?: JsonMap) => Promise<unknown>
  }
  awards: {
    list: (params?: JsonMap) => Promise<unknown>
    byRequest: (requestId: string) => Promise<unknown>
    get: (awardId: string) => Promise<unknown>
  }
  escalations: {
    queue: () => Promise<unknown>
    byRequest: (requestId: string) => Promise<unknown>
  }
  policies: {
    approvalThresholds: (currency?: string) => Promise<unknown>
    approvalThreshold: (thresholdId: string) => Promise<unknown>
    preferredSuppliers: (params?: JsonMap) => Promise<unknown>
    preferredSupplier: (policyId: number) => Promise<unknown>
    restrictedSuppliers: (params?: JsonMap) => Promise<unknown>
    restrictedSupplier: (policyId: number) => Promise<unknown>
  }
  rules: {
    category: (categoryId?: number) => Promise<unknown>
    categoryById: (ruleId: string) => Promise<unknown>
    geography: (country?: string) => Promise<unknown>
    geographyById: (ruleId: string) => Promise<unknown>
    escalation: () => Promise<unknown>
    escalationById: (ruleId: string) => Promise<unknown>
  }
  analytics: {
    compliantSuppliers: (params: JsonMap) => Promise<unknown>
    pricingLookup: (params: JsonMap) => Promise<unknown>
    approvalTier: (currency: string, amount: number | string) => Promise<unknown>
    checkRestricted: (params: JsonMap) => Promise<unknown>
    checkPreferred: (params: JsonMap) => Promise<unknown>
    applicableRules: (params: JsonMap) => Promise<unknown>
    requestOverview: (requestId: string) => Promise<unknown>
    spendByCategory: () => Promise<unknown>
    spendBySupplier: () => Promise<unknown>
    supplierWinRates: () => Promise<unknown>
  }
  orgLogs: {
    runs: {
      create: (payload: JsonMap) => Promise<unknown>
      list: (params?: JsonMap) => Promise<unknown>
      get: (runId: string) => Promise<unknown>
      update: (runId: string, payload: JsonMap) => Promise<unknown>
      byRequest: (requestId: string) => Promise<unknown>
    }
    entries: {
      create: (payload: JsonMap) => Promise<unknown>
      update: (entryId: number, payload: JsonMap) => Promise<unknown>
    }
    audit: {
      create: (payload: JsonMap) => Promise<unknown>
      createBatch: (payload: JsonMap) => Promise<unknown>
      list: (params?: JsonMap) => Promise<unknown>
      byRequest: (requestId: string, params?: JsonMap) => Promise<unknown>
      summary: (requestId: string) => Promise<unknown>
    }
  }
  health: {
    org: () => Promise<unknown>
    logical: () => Promise<unknown>
  }
}

const client = chainIqApi as unknown as ApiClientShape

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) return error.message
  return "Unexpected API error"
}

function isRunInstability(error: unknown): boolean {
  const message = errorMessage(error)
  return message.includes("/api/logs/runs") || message.includes("/api/logs/by-request")
}

function todayPlus(days: number): string {
  const date = new Date(Date.now() + days * 24 * 60 * 60 * 1000)
  return date.toISOString().slice(0, 10)
}

export function DataPage() {
  const [requestId, setRequestId] = useState("REQ-000004")
  const [requestIdForCreate, setRequestIdForCreate] = useState("")
  const [categoryId, setCategoryId] = useState("1")
  const [supplierId, setSupplierId] = useState("SUP-0001")
  const [awardId, setAwardId] = useState("AWD-000001")
  const [thresholdId, setThresholdId] = useState("AT-001")
  const [policyId, setPolicyId] = useState("1")
  const [ruleId, setRuleId] = useState("GR-001")
  const [runId, setRunId] = useState("")
  const [entryId, setEntryId] = useState("1")

  const [categoryL1, setCategoryL1] = useState("IT")
  const [categoryL2, setCategoryL2] = useState("Docking Stations")
  const [deliveryCountry, setDeliveryCountry] = useState("DE")
  const [region, setRegion] = useState("EU")
  const [currency, setCurrency] = useState("EUR")
  const [amount, setAmount] = useState("25199.55")
  const [quantity, setQuantity] = useState("240")

  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fallback, setFallback] = useState<string | null>(null)
  const [result, setResult] = useState<{ title: string; value: unknown } | null>(null)

  const generatedRequestId = useMemo(() => {
    const suffix = String(Date.now()).slice(-6)
    return `REQ-${suffix}`
  }, [])

  async function runAction(
    actionId: string,
    title: string,
    fn: () => Promise<unknown>,
  ) {
    setLoading(actionId)
    setError(null)
    setFallback(null)

    try {
      const value = await fn()
      setResult({ title, value })
    } catch (actionError) {
      if (isRunInstability(actionError)) {
        setFallback(errorMessage(actionError))
      } else {
        setError(errorMessage(actionError))
      }
    } finally {
      setLoading(null)
    }
  }

  const requestCreatePayload: JsonMap = {
    request_id: requestIdForCreate.trim() || generatedRequestId,
    created_at: new Date().toISOString(),
    request_channel: "portal",
    request_language: "en",
    business_unit: "Demo Unit",
    country: deliveryCountry,
    site: "Zurich",
    requester_id: "USR-9000",
    submitted_for_id: "USR-9001",
    category_id: Number(categoryId),
    title: "Demo request from Data page",
    request_text: "Auto-generated test request from UI data explorer.",
    currency,
    budget_amount: Number(amount),
    quantity: Number(quantity),
    unit_of_measure: "device",
    required_by_date: todayPlus(14),
    contract_type_requested: "purchase",
  }

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Data"
        title="Backend endpoint explorer"
        description="Operational and admin workspace exposing all org-layer endpoint groups, including CRUD, policies, rules, analytics, and logs."
      />

      {error ? <ErrorStateCard title="Action failed" description={error} /> : null}
      {fallback ? (
        <FallbackBanner
          title="Logs/runs endpoint degraded"
          detail={`Known instability detected for org log run endpoints. Other endpoint groups remain operational. ${fallback}`}
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Requests CRUD</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={requestId} onChange={(e) => setRequestId(e.target.value)} placeholder="Request ID" />
            <Input value={categoryId} onChange={(e) => setCategoryId(e.target.value)} placeholder="Category ID" />
            <Input
              value={requestIdForCreate}
              onChange={(e) => setRequestIdForCreate(e.target.value)}
              placeholder={`Create ID (blank => ${generatedRequestId})`}
            />
            <div className="flex flex-wrap gap-2">
              <RunBtn label="List" loading={loading === "req-list"} onClick={() => runAction("req-list", "Requests / List", () => client.requests.list({ limit: 50, skip: 0 }))} />
              <RunBtn label="Get" loading={loading === "req-get"} onClick={() => runAction("req-get", "Requests / Get", () => client.requests.get(requestId.trim()))} />
              <RunBtn label="Create" loading={loading === "req-create"} onClick={() => runAction("req-create", "Requests / Create", () => client.requests.create(requestCreatePayload))} />
              <RunBtn label="Update" loading={loading === "req-update"} onClick={() => runAction("req-update", "Requests / Update", () => client.requests.update(requestId.trim(), { status: "pending_review" }))} />
              <RunBtn label="Delete" loading={loading === "req-delete"} onClick={() => runAction("req-delete", "Requests / Delete", async () => {
                await client.requests.remove(requestId.trim())
                return { deleted: true, request_id: requestId.trim() }
              })} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Categories CRUD</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={categoryId} onChange={(e) => setCategoryId(e.target.value)} placeholder="Category ID" />
            <div className="flex flex-wrap gap-2">
              <RunBtn label="List" loading={loading === "cat-list"} onClick={() => runAction("cat-list", "Categories / List", () => client.categories.list())} />
              <RunBtn label="Get" loading={loading === "cat-get"} onClick={() => runAction("cat-get", "Categories / Get", () => client.categories.get(Number(categoryId)))} />
              <RunBtn label="Create" loading={loading === "cat-create"} onClick={() => runAction("cat-create", "Categories / Create", () => client.categories.create({
                category_l1: "IT",
                category_l2: `Demo ${Date.now()}`,
                category_description: "UI-created demo category",
                typical_unit: "unit",
                pricing_model: "tiered",
              }))} />
              <RunBtn label="Update" loading={loading === "cat-update"} onClick={() => runAction("cat-update", "Categories / Update", () => client.categories.update(Number(categoryId), {
                category_description: "Updated from data explorer",
              }))} />
              <RunBtn label="Delete" loading={loading === "cat-delete"} onClick={() => runAction("cat-delete", "Categories / Delete", async () => {
                await client.categories.remove(Number(categoryId))
                return { deleted: true, category_id: Number(categoryId) }
              })} />
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Suppliers + subresources</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={supplierId} onChange={(e) => setSupplierId(e.target.value)} placeholder="Supplier ID" />
            <div className="flex flex-wrap gap-2">
              <RunBtn label="List" loading={loading === "sup-list"} onClick={() => runAction("sup-list", "Suppliers / List", () => client.suppliers.list({ category_l1: categoryL1 }))} />
              <RunBtn label="Get" loading={loading === "sup-get"} onClick={() => runAction("sup-get", "Suppliers / Get", () => client.suppliers.get(supplierId.trim()))} />
              <RunBtn label="Create" loading={loading === "sup-create"} onClick={() => runAction("sup-create", "Suppliers / Create", () => client.suppliers.create({
                supplier_id: `SUP-${Date.now()}`,
                supplier_name: "UI Demo Supplier",
                country_hq: deliveryCountry,
                currency,
                contract_status: "active",
                capacity_per_month: 1000,
              }))} />
              <RunBtn label="Update" loading={loading === "sup-update"} onClick={() => runAction("sup-update", "Suppliers / Update", () => client.suppliers.update(supplierId.trim(), {
                contract_status: "active",
              }))} />
              <RunBtn label="Delete" loading={loading === "sup-delete"} onClick={() => runAction("sup-delete", "Suppliers / Delete", async () => {
                await client.suppliers.remove(supplierId.trim())
                return { deleted: true, supplier_id: supplierId.trim() }
              })} />
              <RunBtn label="Categories" loading={loading === "sup-categories"} onClick={() => runAction("sup-categories", "Suppliers / Categories", () => client.suppliers.categories(supplierId.trim()))} />
              <RunBtn label="Regions" loading={loading === "sup-regions"} onClick={() => runAction("sup-regions", "Suppliers / Regions", () => client.suppliers.regions(supplierId.trim()))} />
              <RunBtn label="Pricing" loading={loading === "sup-pricing"} onClick={() => runAction("sup-pricing", "Suppliers / Pricing", () => client.suppliers.pricing(supplierId.trim(), {
                category_id: Number(categoryId),
                region,
              }))} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Awards + escalations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={awardId} onChange={(e) => setAwardId(e.target.value)} placeholder="Award ID" />
            <Input value={requestId} onChange={(e) => setRequestId(e.target.value)} placeholder="Request ID" />
            <div className="flex flex-wrap gap-2">
              <RunBtn label="Awards List" loading={loading === "awd-list"} onClick={() => runAction("awd-list", "Awards / List", () => client.awards.list({ limit: 50, skip: 0 }))} />
              <RunBtn label="By Request" loading={loading === "awd-by-request"} onClick={() => runAction("awd-by-request", "Awards / By Request", () => client.awards.byRequest(requestId.trim()))} />
              <RunBtn label="Get Award" loading={loading === "awd-get"} onClick={() => runAction("awd-get", "Awards / Get", () => client.awards.get(awardId.trim()))} />
              <RunBtn label="Esc Queue" loading={loading === "esc-queue"} onClick={() => runAction("esc-queue", "Escalations / Queue", () => client.escalations.queue())} />
              <RunBtn label="Esc By Request" loading={loading === "esc-by-request"} onClick={() => runAction("esc-by-request", "Escalations / By Request", () => client.escalations.byRequest(requestId.trim()))} />
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Policies + rules</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={thresholdId} onChange={(e) => setThresholdId(e.target.value)} placeholder="Threshold ID" />
            <Input value={policyId} onChange={(e) => setPolicyId(e.target.value)} placeholder="Policy ID" type="number" />
            <Input value={ruleId} onChange={(e) => setRuleId(e.target.value)} placeholder="Rule ID" />
            <div className="flex flex-wrap gap-2">
              <RunBtn label="AT List" loading={loading === "pol-at-list"} onClick={() => runAction("pol-at-list", "Policies / Approval Thresholds", () => client.policies.approvalThresholds(currency))} />
              <RunBtn label="AT Get" loading={loading === "pol-at-get"} onClick={() => runAction("pol-at-get", "Policies / Approval Threshold", () => client.policies.approvalThreshold(thresholdId.trim()))} />
              <RunBtn label="Preferred List" loading={loading === "pol-pref-list"} onClick={() => runAction("pol-pref-list", "Policies / Preferred List", () => client.policies.preferredSuppliers({ category_l1: categoryL1 }))} />
              <RunBtn label="Preferred Get" loading={loading === "pol-pref-get"} onClick={() => runAction("pol-pref-get", "Policies / Preferred Get", () => client.policies.preferredSupplier(Number(policyId)))} />
              <RunBtn label="Restricted List" loading={loading === "pol-res-list"} onClick={() => runAction("pol-res-list", "Policies / Restricted List", () => client.policies.restrictedSuppliers({ supplier_id: supplierId }))} />
              <RunBtn label="Restricted Get" loading={loading === "pol-res-get"} onClick={() => runAction("pol-res-get", "Policies / Restricted Get", () => client.policies.restrictedSupplier(Number(policyId)))} />
              <RunBtn label="Rule Category" loading={loading === "rule-cat-list"} onClick={() => runAction("rule-cat-list", "Rules / Category List", () => client.rules.category(Number(categoryId)))} />
              <RunBtn label="Rule Cat Get" loading={loading === "rule-cat-get"} onClick={() => runAction("rule-cat-get", "Rules / Category Get", () => client.rules.categoryById(ruleId.trim()))} />
              <RunBtn label="Rule Geo" loading={loading === "rule-geo-list"} onClick={() => runAction("rule-geo-list", "Rules / Geography List", () => client.rules.geography(deliveryCountry))} />
              <RunBtn label="Rule Geo Get" loading={loading === "rule-geo-get"} onClick={() => runAction("rule-geo-get", "Rules / Geography Get", () => client.rules.geographyById(ruleId.trim()))} />
              <RunBtn label="Rule Esc" loading={loading === "rule-esc-list"} onClick={() => runAction("rule-esc-list", "Rules / Escalation List", () => client.rules.escalation())} />
              <RunBtn label="Rule Esc Get" loading={loading === "rule-esc-get"} onClick={() => runAction("rule-esc-get", "Rules / Escalation Get", () => client.rules.escalationById(ruleId.trim()))} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Analytics lab</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input value={categoryL1} onChange={(e) => setCategoryL1(e.target.value)} placeholder="Category L1" />
              <Input value={categoryL2} onChange={(e) => setCategoryL2(e.target.value)} placeholder="Category L2" />
              <Input value={deliveryCountry} onChange={(e) => setDeliveryCountry(e.target.value)} placeholder="Delivery country" />
              <Input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="Region" />
              <Input value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="Currency" />
              <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount" />
              <Input value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="Quantity" />
              <Input value={supplierId} onChange={(e) => setSupplierId(e.target.value)} placeholder="Supplier ID" />
            </div>
            <div className="flex flex-wrap gap-2">
              <RunBtn label="Compliant" loading={loading === "ana-compliant"} onClick={() => runAction("ana-compliant", "Analytics / Compliant Suppliers", () => client.analytics.compliantSuppliers({
                category_l1: categoryL1,
                category_l2: categoryL2,
                delivery_country: deliveryCountry,
              }))} />
              <RunBtn label="Pricing" loading={loading === "ana-pricing"} onClick={() => runAction("ana-pricing", "Analytics / Pricing Lookup", () => client.analytics.pricingLookup({
                supplier_id: supplierId,
                category_l1: categoryL1,
                category_l2: categoryL2,
                region,
                quantity: Number(quantity),
              }))} />
              <RunBtn label="Tier" loading={loading === "ana-tier"} onClick={() => runAction("ana-tier", "Analytics / Approval Tier", () => client.analytics.approvalTier(currency, Number(amount)))} />
              <RunBtn label="Restricted" loading={loading === "ana-restricted"} onClick={() => runAction("ana-restricted", "Analytics / Check Restricted", () => client.analytics.checkRestricted({
                supplier_id: supplierId,
                category_l1: categoryL1,
                category_l2: categoryL2,
                delivery_country: deliveryCountry,
              }))} />
              <RunBtn label="Preferred" loading={loading === "ana-preferred"} onClick={() => runAction("ana-preferred", "Analytics / Check Preferred", () => client.analytics.checkPreferred({
                supplier_id: supplierId,
                category_l1: categoryL1,
                category_l2: categoryL2,
                region,
              }))} />
              <RunBtn label="Rules" loading={loading === "ana-rules"} onClick={() => runAction("ana-rules", "Analytics / Applicable Rules", () => client.analytics.applicableRules({
                category_l1: categoryL1,
                category_l2: categoryL2,
                delivery_country: deliveryCountry,
              }))} />
              <RunBtn label="Overview" loading={loading === "ana-overview"} onClick={() => runAction("ana-overview", "Analytics / Request Overview", () => client.analytics.requestOverview(requestId.trim()))} />
              <RunBtn label="Spend Cat" loading={loading === "ana-spend-cat"} onClick={() => runAction("ana-spend-cat", "Analytics / Spend by Category", () => client.analytics.spendByCategory())} />
              <RunBtn label="Spend Supplier" loading={loading === "ana-spend-sup"} onClick={() => runAction("ana-spend-sup", "Analytics / Spend by Supplier", () => client.analytics.spendBySupplier())} />
              <RunBtn label="Win Rates" loading={loading === "ana-win"} onClick={() => runAction("ana-win", "Analytics / Supplier Win Rates", () => client.analytics.supplierWinRates())} />
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Org logs API</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="Run ID" />
            <Input value={entryId} onChange={(e) => setEntryId(e.target.value)} placeholder="Entry ID" type="number" />
            <Textarea
              className="min-h-16"
              value={requestId}
              onChange={(e) => setRequestId(e.target.value)}
              placeholder="Request ID"
            />
            <div className="flex flex-wrap gap-2">
              <RunBtn label="Runs List" loading={loading === "log-runs-list"} onClick={() => runAction("log-runs-list", "Org Logs / Runs List", () => client.orgLogs.runs.list({ limit: 50, skip: 0 }))} />
              <RunBtn label="Runs Get" loading={loading === "log-runs-get"} onClick={() => runAction("log-runs-get", "Org Logs / Runs Get", () => client.orgLogs.runs.get(runId.trim()))} />
              <RunBtn label="Runs By Req" loading={loading === "log-runs-by-req"} onClick={() => runAction("log-runs-by-req", "Org Logs / Runs By Request", () => client.orgLogs.runs.byRequest(requestId.trim()))} />
              <RunBtn label="Runs Create" loading={loading === "log-runs-create"} onClick={() => runAction("log-runs-create", "Org Logs / Runs Create", () => client.orgLogs.runs.create({
                run_id: `run-${Date.now()}`,
                request_id: requestId.trim(),
                started_at: new Date().toISOString(),
              }))} />
              <RunBtn label="Runs Update" loading={loading === "log-runs-update"} onClick={() => runAction("log-runs-update", "Org Logs / Runs Update", () => client.orgLogs.runs.update(runId.trim(), {
                status: "completed",
                completed_at: new Date().toISOString(),
              }))} />
              <RunBtn label="Entry Create" loading={loading === "log-entry-create"} onClick={() => runAction("log-entry-create", "Org Logs / Entry Create", () => client.orgLogs.entries.create({
                run_id: runId.trim(),
                step_name: "ui-test",
                step_order: 1,
                started_at: new Date().toISOString(),
              }))} />
              <RunBtn label="Entry Update" loading={loading === "log-entry-update"} onClick={() => runAction("log-entry-update", "Org Logs / Entry Update", () => client.orgLogs.entries.update(Number(entryId), {
                status: "completed",
                completed_at: new Date().toISOString(),
              }))} />
              <RunBtn label="Audit List" loading={loading === "log-audit-list"} onClick={() => runAction("log-audit-list", "Org Logs / Audit List", () => client.orgLogs.audit.list({ limit: 100, skip: 0 }))} />
              <RunBtn label="Audit By Req" loading={loading === "log-audit-by-req"} onClick={() => runAction("log-audit-by-req", "Org Logs / Audit By Request", () => client.orgLogs.audit.byRequest(requestId.trim(), { limit: 100, skip: 0 }))} />
              <RunBtn label="Audit Summary" loading={loading === "log-audit-summary"} onClick={() => runAction("log-audit-summary", "Org Logs / Audit Summary", () => client.orgLogs.audit.summary(requestId.trim()))} />
              <RunBtn label="Audit Create" loading={loading === "log-audit-create"} onClick={() => runAction("log-audit-create", "Org Logs / Audit Create", () => client.orgLogs.audit.create({
                request_id: requestId.trim(),
                run_id: runId.trim() || null,
                timestamp: new Date().toISOString(),
                message: "Created from Data explorer",
                level: "info",
                category: "ui",
              }))} />
              <RunBtn label="Audit Batch" loading={loading === "log-audit-batch"} onClick={() => runAction("log-audit-batch", "Org Logs / Audit Batch", () => client.orgLogs.audit.createBatch({
                entries: [
                  {
                    request_id: requestId.trim(),
                    timestamp: new Date().toISOString(),
                    message: "Batch entry from Data explorer",
                  },
                ],
              }))} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Verify connectivity to both organisational and logical backends.
            </p>
            <div className="flex flex-wrap gap-2">
              <RunBtn label="Org Health" loading={loading === "health-org"} onClick={() => runAction("health-org", "Health / Org", () => client.health.org())} />
              <RunBtn label="Logical Health" loading={loading === "health-logical"} onClick={() => runAction("health-logical", "Health / Logical", () => client.health.logical())} />
            </div>
          </CardContent>
        </Card>
      </section>

      {result ? <JsonViewer title={result.title} value={result.value} /> : null}

      {!result ? (
        <EmptyStateCard
          title="No API response yet"
          description="Run any action above to inspect live endpoint payloads and mutations."
        />
      ) : null}
    </div>
  )
}

function RunBtn({
  label,
  loading,
  onClick,
}: {
  label: string
  loading: boolean
  onClick: () => void
}) {
  return (
    <Button variant="outline" size="sm" onClick={onClick} disabled={loading}>
      {loading ? <Database className="size-3.5 animate-pulse" /> : <Search className="size-3.5" />}
      {label}
    </Button>
  )
}
