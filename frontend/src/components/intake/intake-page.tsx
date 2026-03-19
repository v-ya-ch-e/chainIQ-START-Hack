"use client"

import { useEffect, useMemo, useState } from "react"
import { Play, Upload } from "lucide-react"

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
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

interface CategoryOut {
  id: number
  category_l1: string
  category_l2: string
}

interface RequestListOut {
  items: Array<{ request_id: string }>
  total: number
  skip: number
  limit: number
}

interface ParseResponse {
  complete: boolean
  request: Record<string, unknown>
}

interface RequestOut {
  request_id: string
  [key: string]: unknown
}

interface ApiClientShape {
  parse: {
    parseText: (body: { text: string }) => Promise<ParseResponse>
    parseFile: (file: File) => Promise<ParseResponse>
  }
  requests: {
    list: (params?: Record<string, string | number | boolean>) => Promise<RequestListOut>
    create: (payload: Record<string, unknown>) => Promise<RequestOut>
  }
  categories: {
    list: () => Promise<CategoryOut[]>
  }
  pipeline: {
    process: (payload: { request_id: string }) => Promise<unknown>
    status: (requestId: string) => Promise<unknown>
    auditSummary: (requestId: string) => Promise<unknown>
  }
}

const client = chainIqApi as unknown as ApiClientShape

type RequestFormState = {
  request_id: string
  created_at: string
  request_channel: string
  request_language: string
  business_unit: string
  country: string
  site: string
  requester_id: string
  requester_role: string
  submitted_for_id: string
  category_id: string
  category_l1: string
  category_l2: string
  title: string
  request_text: string
  currency: string
  budget_amount: string
  quantity: string
  unit_of_measure: string
  required_by_date: string
  preferred_supplier_mentioned: string
  incumbent_supplier: string
  contract_type_requested: string
  data_residency_constraint: boolean
  esg_requirement: boolean
  delivery_countries: string
  scenario_tags: string
}

function nowIsoWithoutMs() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z")
}

function toLocalDate(value: string) {
  if (!value) return ""
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ""
  return parsed.toISOString().slice(0, 10)
}

function toStringValue(value: unknown): string {
  if (value === undefined || value === null) return ""
  return String(value)
}

function mapParsedRequestToForm(
  parsed: Record<string, unknown>,
  categories: CategoryOut[],
  suggestedId: string,
): RequestFormState {
  const categoryL1 = toStringValue(parsed.category_l1)
  const categoryL2 = toStringValue(parsed.category_l2)
  const matchedCategory = categories.find(
    (entry) => entry.category_l1 === categoryL1 && entry.category_l2 === categoryL2,
  )

  return {
    request_id: toStringValue(parsed.request_id) || suggestedId,
    created_at: toStringValue(parsed.created_at) || nowIsoWithoutMs(),
    request_channel: toStringValue(parsed.request_channel) || "portal",
    request_language: toStringValue(parsed.request_language) || "en",
    business_unit: toStringValue(parsed.business_unit),
    country: toStringValue(parsed.country),
    site: toStringValue(parsed.site),
    requester_id: toStringValue(parsed.requester_id),
    requester_role: toStringValue(parsed.requester_role),
    submitted_for_id: toStringValue(parsed.submitted_for_id),
    category_id: matchedCategory ? String(matchedCategory.id) : "",
    category_l1: categoryL1,
    category_l2: categoryL2,
    title: toStringValue(parsed.title),
    request_text: toStringValue(parsed.request_text),
    currency: toStringValue(parsed.currency) || "EUR",
    budget_amount: toStringValue(parsed.budget_amount),
    quantity: toStringValue(parsed.quantity),
    unit_of_measure: toStringValue(parsed.unit_of_measure) || "unit",
    required_by_date: toLocalDate(toStringValue(parsed.required_by_date)),
    preferred_supplier_mentioned: toStringValue(parsed.preferred_supplier_mentioned),
    incumbent_supplier: toStringValue(parsed.incumbent_supplier),
    contract_type_requested: toStringValue(parsed.contract_type_requested) || "purchase",
    data_residency_constraint: Boolean(parsed.data_residency_constraint),
    esg_requirement: Boolean(parsed.esg_requirement),
    delivery_countries: Array.isArray(parsed.delivery_countries)
      ? parsed.delivery_countries.join(",")
      : "",
    scenario_tags: Array.isArray(parsed.scenario_tags) ? parsed.scenario_tags.join(",") : "",
  }
}

function buildCreatePayload(form: RequestFormState): Record<string, unknown> {
  return {
    request_id: form.request_id.trim(),
    created_at: form.created_at,
    request_channel: form.request_channel.trim(),
    request_language: form.request_language.trim(),
    business_unit: form.business_unit.trim(),
    country: form.country.trim(),
    site: form.site.trim(),
    requester_id: form.requester_id.trim(),
    requester_role: form.requester_role.trim() || null,
    submitted_for_id: form.submitted_for_id.trim(),
    category_id: Number(form.category_id),
    title: form.title.trim(),
    request_text: form.request_text,
    currency: form.currency.trim(),
    budget_amount: form.budget_amount.trim() ? Number(form.budget_amount) : null,
    quantity: form.quantity.trim() ? Number(form.quantity) : null,
    unit_of_measure: form.unit_of_measure.trim(),
    required_by_date: form.required_by_date,
    preferred_supplier_mentioned: form.preferred_supplier_mentioned.trim() || null,
    incumbent_supplier: form.incumbent_supplier.trim() || null,
    contract_type_requested: form.contract_type_requested.trim(),
    data_residency_constraint: form.data_residency_constraint,
    esg_requirement: form.esg_requirement,
    status: "new",
    delivery_countries: form.delivery_countries
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean),
    scenario_tags: form.scenario_tags
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean),
  }
}

function defaultFormState(suggestedId: string, createdAt = ""): RequestFormState {
  return {
    request_id: suggestedId,
    created_at: createdAt,
    request_channel: "portal",
    request_language: "en",
    business_unit: "",
    country: "",
    site: "",
    requester_id: "",
    requester_role: "",
    submitted_for_id: "",
    category_id: "",
    category_l1: "",
    category_l2: "",
    title: "",
    request_text: "",
    currency: "EUR",
    budget_amount: "",
    quantity: "",
    unit_of_measure: "unit",
    required_by_date: "",
    preferred_supplier_mentioned: "",
    incumbent_supplier: "",
    contract_type_requested: "purchase",
    data_residency_constraint: false,
    esg_requirement: false,
    delivery_countries: "",
    scenario_tags: "",
  }
}

function deriveNextRequestId(requestIds: string[]): string {
  const highest = requestIds.reduce((acc, requestId) => {
    const match = requestId.match(/^REQ-(\d+)$/)
    if (!match) return acc
    const value = Number(match[1])
    return Number.isFinite(value) && value > acc ? value : acc
  }, 0)

  return `REQ-${String(highest + 1).padStart(6, "0")}`
}

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) return error.message
  return "Unexpected error while calling backend"
}

function isRunEndpointInstability(error: unknown): boolean {
  const message = errorMessage(error)
  return (
    message.includes("/api/logs/runs") ||
    message.includes("/api/logs/by-request") ||
    message.includes("Org Layer unreachable")
  )
}

export function IntakePage() {
  const [inputText, setInputText] = useState("")
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [isParsing, setIsParsing] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [categories, setCategories] = useState<CategoryOut[]>([])
  const [suggestedId, setSuggestedId] = useState("REQ-000001")
  const [form, setForm] = useState<RequestFormState>(() => defaultFormState("REQ-000001"))

  const [parsed, setParsed] = useState<ParseResponse | null>(null)
  const [created, setCreated] = useState<RequestOut | null>(null)
  const [triggerResult, setTriggerResult] = useState<unknown>(null)
  const [pipelineStatus, setPipelineStatus] = useState<unknown>(null)
  const [auditSummary, setAuditSummary] = useState<unknown>(null)

  const [error, setError] = useState<string | null>(null)
  const [fallbackDetail, setFallbackDetail] = useState<string | null>(null)

  useEffect(() => {
    setForm((prev) =>
      prev.created_at
        ? prev
        : {
            ...prev,
            created_at: nowIsoWithoutMs(),
          },
    )
  }, [])

  useEffect(() => {
    let active = true

    async function loadBootstrapData() {
      try {
        const [categoryRows, requestRows] = await Promise.all([
          client.categories.list(),
          client.requests.list({ limit: 200, skip: 0 }),
        ])

        if (!active) return

        setCategories(categoryRows)
        const nextId = deriveNextRequestId(requestRows.items.map((entry) => entry.request_id))
        setSuggestedId(nextId)
        setForm((prev) => ({
          ...prev,
          request_id: prev.request_id || nextId,
        }))
      } catch (loadError) {
        if (!active) return
        setError(errorMessage(loadError))
      }
    }

    void loadBootstrapData()

    return () => {
      active = false
    }
  }, [])

  const canSubmit = useMemo(() => {
    return (
      form.request_id.trim() &&
      form.created_at.trim() &&
      form.request_channel.trim() &&
      form.request_language.trim() &&
      form.business_unit.trim() &&
      form.country.trim() &&
      form.site.trim() &&
      form.requester_id.trim() &&
      form.submitted_for_id.trim() &&
      form.category_id.trim() &&
      form.title.trim() &&
      form.request_text.trim() &&
      form.currency.trim() &&
      form.unit_of_measure.trim() &&
      form.required_by_date.trim() &&
      form.contract_type_requested.trim()
    )
  }, [form])

  function updateField<K extends keyof RequestFormState>(key: K, value: RequestFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function parseFromText() {
    if (!inputText.trim()) {
      setError("Provide source text before parsing.")
      return
    }

    setIsParsing(true)
    setError(null)
    setFallbackDetail(null)

    try {
      const payload = await client.parse.parseText({ text: inputText.trim() })
      setParsed(payload)
      setForm((prev) => {
        const mapped = mapParsedRequestToForm(payload.request, categories, suggestedId)
        return {
          ...mapped,
          created_at: mapped.created_at || prev.created_at || nowIsoWithoutMs(),
        }
      })
    } catch (parseError) {
      setError(errorMessage(parseError))
    } finally {
      setIsParsing(false)
    }
  }

  async function parseFromFile() {
    if (!uploadFile) {
      setError("Select a file before parsing.")
      return
    }

    setIsParsing(true)
    setError(null)
    setFallbackDetail(null)

    try {
      const payload = await client.parse.parseFile(uploadFile)
      setParsed(payload)
      setForm((prev) => {
        const mapped = mapParsedRequestToForm(payload.request, categories, suggestedId)
        return {
          ...mapped,
          created_at: mapped.created_at || prev.created_at || nowIsoWithoutMs(),
        }
      })
    } catch (parseError) {
      setError(errorMessage(parseError))
    } finally {
      setIsParsing(false)
    }
  }

  async function refreshPipelineState(requestId: string) {
    try {
      const [status, summary] = await Promise.all([
        client.pipeline.status(requestId),
        client.pipeline.auditSummary(requestId),
      ])
      setPipelineStatus(status)
      setAuditSummary(summary)
      setFallbackDetail(null)
    } catch (stateError) {
      if (isRunEndpointInstability(stateError)) {
        setFallbackDetail(errorMessage(stateError))
        return
      }
      setError(errorMessage(stateError))
    }
  }

  async function createAndTrigger() {
    if (!canSubmit) {
      setError("Fill all required fields before creating the request.")
      return
    }

    setIsSubmitting(true)
    setError(null)
    setFallbackDetail(null)

    try {
      const requestPayload = buildCreatePayload(form)
      const createdRequest = await client.requests.create(requestPayload)
      setCreated(createdRequest)

      const trigger = await client.pipeline.process({
        request_id: createdRequest.request_id,
      })
      setTriggerResult(trigger)

      await refreshPipelineState(createdRequest.request_id)
    } catch (submitError) {
      if (isRunEndpointInstability(submitError)) {
        setFallbackDetail(errorMessage(submitError))
        return
      }
      setError(errorMessage(submitError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Intake"
        title="Parse, review, create, and trigger"
        description="Ingestion workspace for new requests: parse source input, validate structured fields, persist to DB, and start pipeline execution."
      />

      {error ? <ErrorStateCard title="Action failed" description={error} /> : null}
      {fallbackDetail ? (
        <FallbackBanner
          title="Run-status backend degraded"
          detail={`Detected unstable run endpoint behavior. Request creation and trigger can still succeed. ${fallbackDetail}`}
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Parse from text</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              placeholder="Paste free-text request, email, or transcript..."
              className="min-h-36"
            />
            <Button onClick={parseFromText} disabled={isParsing}>
              <Play className="size-3.5" />
              {isParsing ? "Parsing..." : "Parse Text"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Parse from file</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            />
            <p className="text-xs text-muted-foreground">
              Supported formats: PDF and image files.
            </p>
            <Button variant="outline" onClick={parseFromFile} disabled={isParsing}>
              <Upload className="size-3.5" />
              {isParsing ? "Parsing..." : "Parse File"}
            </Button>
          </CardContent>
        </Card>
      </section>

      {parsed ? <JsonViewer title="Parser Output" value={parsed} /> : null}

      <Card>
        <CardHeader>
          <CardTitle>Review and create request</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <InputField label="Request ID" value={form.request_id} onChange={(value) => updateField("request_id", value)} required />
            <InputField label="Created At (ISO)" value={form.created_at} onChange={(value) => updateField("created_at", value)} required />
            <InputField label="Channel" value={form.request_channel} onChange={(value) => updateField("request_channel", value)} required />
            <InputField label="Language" value={form.request_language} onChange={(value) => updateField("request_language", value)} required />
            <InputField label="Business Unit" value={form.business_unit} onChange={(value) => updateField("business_unit", value)} required />
            <InputField label="Country" value={form.country} onChange={(value) => updateField("country", value)} required />
            <InputField label="Site" value={form.site} onChange={(value) => updateField("site", value)} required />
            <InputField label="Requester ID" value={form.requester_id} onChange={(value) => updateField("requester_id", value)} required />
            <InputField label="Requester Role" value={form.requester_role} onChange={(value) => updateField("requester_role", value)} />
            <InputField label="Submitted For ID" value={form.submitted_for_id} onChange={(value) => updateField("submitted_for_id", value)} required />
            <InputField label="Category ID" value={form.category_id} onChange={(value) => updateField("category_id", value)} required />
            <InputField label="Category L1" value={form.category_l1} onChange={(value) => updateField("category_l1", value)} />
            <InputField label="Category L2" value={form.category_l2} onChange={(value) => updateField("category_l2", value)} />
            <InputField label="Currency" value={form.currency} onChange={(value) => updateField("currency", value)} required />
            <InputField label="Budget Amount" value={form.budget_amount} onChange={(value) => updateField("budget_amount", value)} />
            <InputField label="Quantity" value={form.quantity} onChange={(value) => updateField("quantity", value)} />
            <InputField label="Unit Of Measure" value={form.unit_of_measure} onChange={(value) => updateField("unit_of_measure", value)} required />
            <InputField
              label="Required By Date"
              value={form.required_by_date}
              onChange={(value) => updateField("required_by_date", value)}
              required
              type="date"
            />
            <InputField label="Preferred Supplier" value={form.preferred_supplier_mentioned} onChange={(value) => updateField("preferred_supplier_mentioned", value)} />
            <InputField label="Incumbent Supplier" value={form.incumbent_supplier} onChange={(value) => updateField("incumbent_supplier", value)} />
            <InputField
              label="Contract Type"
              value={form.contract_type_requested}
              onChange={(value) => updateField("contract_type_requested", value)}
              required
            />
            <InputField label="Delivery Countries (comma-separated)" value={form.delivery_countries} onChange={(value) => updateField("delivery_countries", value)} />
            <InputField label="Scenario Tags (comma-separated)" value={form.scenario_tags} onChange={(value) => updateField("scenario_tags", value)} />
            <CheckboxField
              label="Data Residency Constraint"
              checked={form.data_residency_constraint}
              onCheckedChange={(value) => updateField("data_residency_constraint", value)}
            />
            <CheckboxField
              label="ESG Requirement"
              checked={form.esg_requirement}
              onCheckedChange={(value) => updateField("esg_requirement", value)}
            />
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Title</p>
            <Input value={form.title} onChange={(event) => updateField("title", event.target.value)} />
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Request Text</p>
            <Textarea
              value={form.request_text}
              onChange={(event) => updateField("request_text", event.target.value)}
              className="min-h-28"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={createAndTrigger} disabled={isSubmitting || !canSubmit}>
              <Play className="size-3.5" />
              {isSubmitting ? "Submitting..." : "Create Request and Trigger Pipeline"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setForm(defaultFormState(suggestedId, nowIsoWithoutMs()))}
              disabled={isSubmitting}
            >
              Reset Form
            </Button>
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4 xl:grid-cols-2">
        {created ? <JsonViewer title="Created Request" value={created} /> : null}
        {triggerResult ? <JsonViewer title="Pipeline Trigger Result" value={triggerResult} /> : null}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        {pipelineStatus ? <JsonViewer title="Pipeline Status" value={pipelineStatus} /> : null}
        {auditSummary ? <JsonViewer title="Pipeline Audit Summary" value={auditSummary} /> : null}
      </section>

      {!parsed && !created ? (
        <EmptyStateCard
          title="No ingestion run yet"
          description="Parse source input to populate fields, then create the request and trigger pipeline execution."
        />
      ) : null}
    </div>
  )
}

function InputField({
  label,
  value,
  onChange,
  required = false,
  type = "text",
}: {
  label: string
  value: string
  onChange: (value: string) => void
  required?: boolean
  type?: string
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
        {required ? " *" : ""}
      </p>
      <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function CheckboxField({
  label,
  checked,
  onCheckedChange,
}: {
  label: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <label className="flex min-h-8 items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm">
      <Checkbox
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      {label}
    </label>
  )
}
