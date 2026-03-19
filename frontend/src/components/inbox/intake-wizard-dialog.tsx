"use client"

import { useEffect, useId, useRef, useState } from "react"
import { Play, Upload, Check, FileText, MessageSquare, ClipboardCheck, AlertCircle, X, Loader2 } from "lucide-react"
import { useRouter } from "next/navigation"
import { useChat } from "@ai-sdk/react"
import { useChatRuntime } from "@assistant-ui/react-ai-sdk"
import { AssistantRuntimeProvider } from "@assistant-ui/react"
import { Thread } from "@/components/assistant-ui/thread"
import type { UploadHookControl } from "@better-upload/client"
import { useUploadFile } from "@better-upload/client"
import { UploadDropzone } from "@/components/ui/upload-dropzone"

import { TooltipProvider } from "@/components/ui/tooltip"

import { chainIqApi } from "@/lib/api/client"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

// ─── Types ────────────────────────────────────────────────────────────────────

export type RequestFormState = {
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

export interface IntakeWizardDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type CategoryRow = {
  id: number
  category_l1: string
  category_l2: string
}

type RequestListResponse = {
  items: Array<{ request_id: string }>
}

type ChatMessageLike = {
  role?: string
  content?: string
}

type ParsedRequestLike = {
  [K in keyof RequestFormState]?: unknown
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function nowIsoWithoutMs() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z")
}

function defaultFormState(suggestedId: string): RequestFormState {
  return {
    request_id: suggestedId,
    created_at: nowIsoWithoutMs(),
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

const REQUIRED_FIELDS: { key: keyof RequestFormState; label: string }[] = [
  { key: "title", label: "Title" },
  { key: "business_unit", label: "Business Unit" },
  { key: "country", label: "Country" },
  { key: "budget_amount", label: "Budget Amount" },
  { key: "quantity", label: "Quantity" },
  { key: "required_by_date", label: "Required By Date" },
]

const REQUIRED_FIELD_KEY_SET = new Set<keyof RequestFormState>(REQUIRED_FIELDS.map((field) => field.key))

function getMissingRequiredFields(form: RequestFormState) {
  return REQUIRED_FIELDS.filter((field) => form[field.key].trim() === "")
}

function asString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value
  if (value === null || value === undefined) return fallback
  return String(value)
}

const client = chainIqApi

// ─── Step Indicator ───────────────────────────────────────────────────────────

const STEPS = [
  { id: 1, label: "Ingest", icon: FileText },
  { id: 2, label: "Refine", icon: MessageSquare },
  { id: 3, label: "Confirm", icon: ClipboardCheck },
] as const

function StepIndicator({
  current,
  onNavigate,
  disabled,
}: {
  current: 1 | 2 | 3
  onNavigate: (step: 1 | 2 | 3) => void
  disabled?: boolean
}) {
  return (
    <div className="flex items-center justify-center gap-1" role="navigation" aria-label="Wizard steps">
      {STEPS.map((s, idx) => {
        const isCompleted = current > s.id
        const isCurrent = current === s.id
        const Icon = s.icon

        return (
          <div key={s.id} className="flex items-center">
            <button
              type="button"
              onClick={() => isCompleted && !disabled && onNavigate(s.id as 1 | 2 | 3)}
              disabled={!isCompleted || disabled}
              className={cn(
                "group flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-all duration-200",
                isCurrent && "bg-primary text-primary-foreground shadow-sm shadow-primary/25",
                isCompleted && "cursor-pointer text-primary hover:bg-primary/10",
                !isCurrent && !isCompleted && "cursor-default text-muted-foreground",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <span className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
                isCurrent && "border-primary-foreground/30 bg-primary-foreground/15",
                isCompleted && "border-primary/30 bg-primary/10",
                !isCurrent && !isCompleted && "border-muted-foreground/30",
              )}>
                {isCompleted ? <Check className="size-3.5" /> : <Icon className="size-3.5" />}
              </span>
              <span className="hidden sm:inline">{s.label}</span>
            </button>
            {idx < STEPS.length - 1 && (
              <div className={cn(
                "mx-1 h-px w-8 transition-colors duration-300",
                current > s.id ? "bg-primary" : "bg-border",
              )} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── Live Form Summary (Step 2 right panel) ──────────────────────────────────

const SUMMARY_FIELDS: { key: keyof RequestFormState; label: string; required?: boolean }[] = [
  { key: "title", label: "Title", required: REQUIRED_FIELD_KEY_SET.has("title") },
  { key: "business_unit", label: "Business Unit", required: REQUIRED_FIELD_KEY_SET.has("business_unit") },
  { key: "country", label: "Country", required: REQUIRED_FIELD_KEY_SET.has("country") },
  { key: "category_l1", label: "Category L1" },
  { key: "category_l2", label: "Category L2" },
  { key: "budget_amount", label: "Budget", required: REQUIRED_FIELD_KEY_SET.has("budget_amount") },
  { key: "currency", label: "Currency" },
  { key: "quantity", label: "Quantity", required: REQUIRED_FIELD_KEY_SET.has("quantity") },
  { key: "required_by_date", label: "Required By", required: REQUIRED_FIELD_KEY_SET.has("required_by_date") },
  { key: "preferred_supplier_mentioned", label: "Preferred Supplier" },
  { key: "delivery_countries", label: "Delivery Countries" },
]

function LiveFormSummary({ form }: { form: RequestFormState }) {
  const filled = SUMMARY_FIELDS.filter((f) => {
    const val = form[f.key]
    return typeof val === "string" ? val.trim() !== "" : val !== false
  }).length
  const total = SUMMARY_FIELDS.length
  const pct = Math.round((filled / total) * 100)

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Completeness</span>
          <span className="tabular-nums font-semibold text-primary">{pct}%</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
        {SUMMARY_FIELDS.map((field) => {
          const val = form[field.key]
          const isEmpty = typeof val === "string" ? val.trim() === "" : !val
          const requiredMissing = Boolean(field.required && isEmpty)
          const optionalEmpty = Boolean(!field.required && isEmpty)

          return (
            <div
              key={field.key}
              className={cn(
                "flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                requiredMissing ? "bg-amber-500/5" : "bg-muted/50",
              )}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className={cn(
                  "size-1.5 rounded-full shrink-0",
                  requiredMissing ? "bg-amber-500" : optionalEmpty ? "bg-muted-foreground/40" : "bg-emerald-500",
                )} />
                <span className={cn(
                  "truncate",
                  isEmpty ? "text-muted-foreground" : "text-foreground",
                )}>
                  {field.label}
                  {field.required && <span className="text-destructive ml-0.5">*</span>}
                </span>
              </div>
              {requiredMissing ? (
                <span className="shrink-0 rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                  Required
                </span>
              ) : optionalEmpty ? (
                <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Optional
                </span>
              ) : (
                <span className="truncate max-w-[45%] text-right text-muted-foreground text-xs">
                  {String(val)}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Form Primitives (Step 3) ────────────────────────────────────────────────

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
        <div className="h-px flex-1 bg-border" />
        <span className="shrink-0 uppercase text-xs tracking-widest text-muted-foreground">{title}</span>
        <div className="h-px flex-1 bg-border" />
      </h3>
      {children}
    </div>
  )
}

function InputField({ label, value, onChange, type = "text", required, placeholder, errorText }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean; placeholder?: string; errorText?: string
}) {
  const inputId = useId()
  const errorId = `${inputId}-error`
  const isEmpty = value.trim() === ""
  const hasError = Boolean(errorText)
  return (
    <div className="space-y-1.5">
      <label htmlFor={inputId} className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
        {label}
        {required && <span className="text-destructive">*</span>}
      </label>
      <Input
        id={inputId}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || label}
        required={required}
        aria-invalid={hasError}
        aria-describedby={hasError ? errorId : undefined}
        className={cn(
          "h-9 transition-colors",
          required && isEmpty && "border-amber-500/40 focus-visible:ring-amber-500/30",
          hasError && "border-destructive/50 focus-visible:ring-destructive/30",
        )}
      />
      {hasError ? (
        <p id={errorId} className="text-xs text-destructive">
          {errorText}
        </p>
      ) : null}
    </div>
  )
}

function SwitchField({ label, checked, onCheckedChange, description }: {
  label: string; checked: boolean; onCheckedChange: (v: boolean) => void; description?: string
}) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3 cursor-pointer hover:bg-muted/30 transition-colors">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200",
          checked ? "bg-primary" : "bg-muted-foreground/25",
        )}
      >
        <span className={cn(
          "inline-block size-3.5 rounded-full bg-white shadow-sm transition-transform duration-200",
          checked ? "translate-x-[18px]" : "translate-x-[3px]",
        )} />
      </button>
    </label>
  )
}

// ─── Main Wizard ─────────────────────────────────────────────────────────────

export function IntakeWizardDialog({ open, onOpenChange }: IntakeWizardDialogProps) {
  const router = useRouter()
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [inputText, setInputText] = useState("")
  const [isParsing, setIsParsing] = useState(false)
  const [submitMode, setSubmitMode] = useState<"trigger" | "draft" | null>(null)
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [categories, setCategories] = useState<CategoryRow[]>([])
  const [suggestedId, setSuggestedId] = useState("REQ-000001")
  const [form, setForm] = useState<RequestFormState>(() => defaultFormState("REQ-000001"))

  const chatBottomRef = useRef<HTMLDivElement>(null)
  const chat = useChat({
    api: "/api/chat/intake",
    body: { formState: form },
  })
  const runtime = useChatRuntime(chat)
  const { messages } = chat
  const isSubmitting = submitMode !== null
  const missingRequiredFields = getMissingRequiredFields(form)
  const missingRequiredFieldKeys = new Set(missingRequiredFields.map((field) => field.key))
  const canSubmit = missingRequiredFields.length === 0

  // Watch for JSON blocks in chat to update form live
  useEffect(() => {
    if (messages.length === 0) return
    const lastMessage = messages[messages.length - 1] as ChatMessageLike | undefined
    if (lastMessage?.role === "assistant") {
      const jsonMatch = lastMessage.content?.match(/```json\n([\s\S]*?)\n```/)
      if (jsonMatch && jsonMatch[1]) {
        try {
          const parsedUpdates = JSON.parse(jsonMatch[1]) as ParsedRequestLike
          setForm((prev) => {
            const updated = { ...prev }
            let hasChanges = false
            for (const [k, v] of Object.entries(parsedUpdates)) {
              if (k in updated) {
                const key = k as keyof RequestFormState
                const current = updated[key]
                if (typeof current === "boolean") {
                  const normalized = Boolean(v)
                  if (current !== normalized) {
                    updated[key] = normalized as RequestFormState[keyof RequestFormState]
                    hasChanges = true
                  }
                } else {
                  const normalized = asString(v)
                  if (current !== normalized) {
                    updated[key] = normalized as RequestFormState[keyof RequestFormState]
                    hasChanges = true
                  }
                }
              }
            }
            return hasChanges ? updated : prev
          })
        } catch {
          // ignore partial JSON while streaming
        }
      }
    }
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Bootstrap categories + next ID
  useEffect(() => {
    let active = true
    async function loadBootstrapData() {
      try {
        const [categoryRows, requestRows] = await Promise.all([
          client.categories.list(),
          client.requests.list({ limit: 200, skip: 0 }),
        ]) as [CategoryRow[], RequestListResponse]
        if (!active) return

        setCategories(categoryRows)
        const requestIds = requestRows.items.map((entry) => entry.request_id)
        const highest = requestIds.reduce((acc: number, requestId: string) => {
          const match = requestId.match(/^REQ-(\d+)$/)
          if (!match) return acc
          const value = Number(match[1])
          return Number.isFinite(value) && value > acc ? value : acc
        }, 0)
        
        const nextId = `REQ-${String(highest + 1).padStart(6, "0")}`
        setSuggestedId(nextId)
        setForm((prev) => ({ ...prev, request_id: prev.request_id || nextId }))
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : "Failed to load initial data")
      }
    }
    if (open) {
      void loadBootstrapData()
      setStep(1)
      setError(null)
      setSubmitAttempted(false)
    }
    return () => { active = false }
  }, [open])

  function mapParsedToForm(parsed: ParsedRequestLike) {
    const categoryL1 = asString(parsed.category_l1)
    const categoryL2 = asString(parsed.category_l2)
    const matchedCategory = categories.find(
      (entry) => entry.category_l1 === categoryL1 && entry.category_l2 === categoryL2,
    )

    setForm({
      request_id: asString(parsed.request_id, suggestedId),
      created_at: asString(parsed.created_at, nowIsoWithoutMs()),
      request_channel: asString(parsed.request_channel, "portal"),
      request_language: asString(parsed.request_language, "en"),
      business_unit: asString(parsed.business_unit),
      country: asString(parsed.country),
      site: asString(parsed.site),
      requester_id: asString(parsed.requester_id),
      requester_role: asString(parsed.requester_role),
      submitted_for_id: asString(parsed.submitted_for_id),
      category_id: matchedCategory ? String(matchedCategory.id) : "",
      category_l1: categoryL1,
      category_l2: categoryL2,
      title: asString(parsed.title),
      request_text: asString(parsed.request_text, inputText),
      currency: asString(parsed.currency, "EUR"),
      budget_amount: parsed.budget_amount ? asString(parsed.budget_amount) : "",
      quantity: parsed.quantity ? asString(parsed.quantity) : "",
      unit_of_measure: asString(parsed.unit_of_measure, "unit"),
      required_by_date: parsed.required_by_date ? asString(parsed.required_by_date).slice(0, 10) : "",
      preferred_supplier_mentioned: asString(parsed.preferred_supplier_mentioned),
      incumbent_supplier: asString(parsed.incumbent_supplier),
      contract_type_requested: asString(parsed.contract_type_requested, "purchase"),
      data_residency_constraint: Boolean(parsed.data_residency_constraint),
      esg_requirement: Boolean(parsed.esg_requirement),
      delivery_countries: Array.isArray(parsed.delivery_countries) ? parsed.delivery_countries.join(",") : "",
      scenario_tags: Array.isArray(parsed.scenario_tags) ? parsed.scenario_tags.join(",") : "",
    })
  }

  async function handleParseText() {
    if (!inputText.trim()) {
      setError("Provide source text before parsing.")
      return
    }
    setIsParsing(true)
    setError(null)
    try {
      const payload = await client.parse.parseText({ text: inputText.trim() })
      mapParsedToForm(payload.request)
      setStep(2)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Parse failed")
    } finally {
      setIsParsing(false)
    }
  }

  async function handleParseFile(file: File) {
    setIsParsing(true)
    setError(null)
    try {
      const payload = await client.parse.parseFile(file)
      mapParsedToForm(payload.request)
      setStep(2)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Parse failed")
    } finally {
      setIsParsing(false)
    }
  }

  const { control: uploadControl } = useUploadFile({
    route: "inbox",
  } as { route: string })

  function updateField(key: keyof RequestFormState, value: string | boolean) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function submitRequest(triggerPipeline: boolean) {
    if (triggerPipeline) {
      const missing = getMissingRequiredFields(form)
      if (missing.length > 0) {
        setSubmitAttempted(true)
        setError("Complete all required fields before submitting.")
        return
      }
    }

    setSubmitMode(triggerPipeline ? "trigger" : "draft")
    setSubmitAttempted(triggerPipeline)
    setError(null)
    try {
      const requestPayload = {
         ...form,
         category_id: Number(form.category_id) || null,
         budget_amount: form.budget_amount ? Number(form.budget_amount) : null,
         quantity: form.quantity ? Number(form.quantity) : null,
         delivery_countries: form.delivery_countries.split(",").map(s => s.trim()).filter(Boolean),
         scenario_tags: form.scenario_tags.split(",").map(s => s.trim()).filter(Boolean),
         status: "new"
      }
      
      const createdReq = await client.requests.create(requestPayload)
      if (triggerPipeline) {
        await client.pipeline.process({ request_id: createdReq.request_id })
      }
      onOpenChange(false)
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed")
    } finally {
      setSubmitMode(null)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (isSubmitting) return
        onOpenChange(nextOpen)
      }}
    >
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col p-0 gap-0">
        {/* ── Header ── */}
        <div className="px-6 pt-6 pb-4 border-b space-y-4">
          <DialogHeader>
            <DialogTitle className="text-xl">New Purchase Request</DialogTitle>
            <DialogDescription>
              {step === 1 && "Parse unstructured text or files to extract request details automatically."}
              {step === 2 && "Chat with AI to refine extracted details before final review."}
              {step === 3 && "Review, complete required fields, and submit your request."}
            </DialogDescription>
          </DialogHeader>
          <StepIndicator current={step} onNavigate={setStep} disabled={isSubmitting} />
        </div>

        {/* ── Error Banner ── */}
        {error && (
          <div className="mx-6 mt-4 flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0 mt-0.5" />
            <p className="flex-1">{error}</p>
            <button type="button" onClick={() => setError(null)} className="shrink-0 hover:opacity-70 transition-opacity">
              <X className="size-4" />
            </button>
          </div>
        )}

        {/* ── Body ── */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {/* ── Parsing Overlay ── */}
          {isParsing && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm rounded-xl">
              <div className="flex flex-col items-center gap-3 text-center">
                <Loader2 className="size-8 animate-spin text-primary" />
                <p className="text-sm font-medium">Parsing your input...</p>
                <p className="text-xs text-muted-foreground">Extracting fields from unstructured data</p>
              </div>
            </div>
          )}

          {/* ── Step 1: Ingest ── */}
          {step === 1 && (
            <div className="animate-fade-in-up space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                {/* Text Card */}
                <Card className="overflow-hidden">
                  <CardContent className="flex flex-col gap-4 p-5 h-full">
                    <div className="flex items-center gap-2">
                      <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <FileText className="size-4" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-sm">Parse from Text</h3>
                        <p className="text-xs text-muted-foreground">Paste an email, request, or transcript</p>
                      </div>
                    </div>
                    <Textarea
                      value={inputText}
                      onChange={(event) => setInputText(event.target.value)}
                      placeholder="e.g. &quot;We need 500 ergonomic office chairs for our Munich office by Q2 2026. Budget is around €150,000. Please check Dell and Steelcase...&quot;"
                      className="min-h-[200px] resize-none flex-1 text-sm"
                    />
                    <Button onClick={handleParseText} disabled={isParsing || isSubmitting || !inputText.trim()} className="w-full">
                      <Play className="mr-2 size-4" />
                      Parse Text
                    </Button>
                  </CardContent>
                </Card>

                {/* File Card */}
                <Card className="overflow-hidden">
                  <CardContent className="flex flex-col gap-4 p-5 h-full">
                    <div className="flex items-center gap-2">
                      <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <Upload className="size-4" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-sm">Parse from File</h3>
                        <p className="text-xs text-muted-foreground">Upload a PDF or image document</p>
                      </div>
                    </div>
                    <div className="flex-1 flex items-center justify-center min-h-[200px]">
                      <UploadDropzone
                        control={uploadControl as UploadHookControl<true>}
                        accept="application/pdf,image/*"
                        description="Supported formats: PDF and image files."
                        uploadOverride={(files) => {
                          if (isSubmitting) return
                          if (files.length > 0) {
                            handleParseFile(files[0])
                          }
                        }}
                      />
                    </div>
                  </CardContent>
                </Card>
              </div>

              <div className="flex items-center justify-center pt-2">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  disabled={isSubmitting}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors underline underline-offset-4 decoration-muted-foreground/40"
                >
                  Or skip directly to AI chat →
                </button>
              </div>
            </div>
          )}
          
          {/* ── Step 2: AI Refinement ── */}
          {step === 2 && (
            <div className="animate-fade-in-up grid h-[520px] gap-6 md:grid-cols-[1fr_320px]">
              {/* Chat Panel */}
              <div className="flex flex-col overflow-hidden rounded-xl border bg-card">
                <TooltipProvider>
                  <AssistantRuntimeProvider runtime={runtime}>
                    <Thread />
                  </AssistantRuntimeProvider>
                </TooltipProvider>
              </div>

              {/* Live Summary Panel */}
              <div className="flex flex-col gap-4">
                <Card className="flex-1 overflow-hidden">
                  <CardContent className="p-4 h-full">
                    <LiveFormSummary form={form} />
                  </CardContent>
                </Card>
                <div className="flex justify-between items-center">
                  <Button variant="ghost" size="sm" onClick={() => setStep(1)} disabled={isSubmitting}>
                    ← Back
                  </Button>
                  <Button onClick={() => setStep(3)} size="sm" disabled={isSubmitting}>
                    Continue to Review →
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* ── Step 3: Review & Submit ── */}
          {step === 3 && (
            <div className="animate-fade-in-up space-y-6">
              <FormSection title="Identity">
                <div className="grid gap-4 md:grid-cols-2">
                  <InputField label="Request ID" value={form.request_id} onChange={(v) => updateField("request_id", v)} />
                  <InputField
                    label="Title"
                    value={form.title}
                    onChange={(v) => updateField("title", v)}
                    required
                    errorText={submitAttempted && missingRequiredFieldKeys.has("title") ? "Title is required." : undefined}
                  />
                </div>
                <Textarea
                  value={form.request_text}
                  onChange={(e) => updateField("request_text", e.target.value)}
                  placeholder="Original request text..."
                  className="min-h-[100px] text-sm mt-2"
                />
              </FormSection>

              <FormSection title="Organization">
                <div className="grid gap-4 md:grid-cols-3">
                  <InputField
                    label="Business Unit"
                    value={form.business_unit}
                    onChange={(v) => updateField("business_unit", v)}
                    required
                    errorText={submitAttempted && missingRequiredFieldKeys.has("business_unit") ? "Business Unit is required." : undefined}
                  />
                  <InputField
                    label="Country"
                    value={form.country}
                    onChange={(v) => updateField("country", v)}
                    required
                    errorText={submitAttempted && missingRequiredFieldKeys.has("country") ? "Country is required." : undefined}
                  />
                  <InputField label="Site" value={form.site} onChange={(v) => updateField("site", v)} />
                  <InputField label="Requester ID" value={form.requester_id} onChange={(v) => updateField("requester_id", v)} />
                  <InputField label="Requester Role" value={form.requester_role} onChange={(v) => updateField("requester_role", v)} />
                  <InputField label="Submitted For" value={form.submitted_for_id} onChange={(v) => updateField("submitted_for_id", v)} />
                </div>
              </FormSection>

              <FormSection title="Category">
                <div className="grid gap-4 md:grid-cols-3">
                  <InputField label="Category L1" value={form.category_l1} onChange={(v) => updateField("category_l1", v)} />
                  <InputField label="Category L2" value={form.category_l2} onChange={(v) => updateField("category_l2", v)} />
                  <InputField label="Contract Type" value={form.contract_type_requested} onChange={(v) => updateField("contract_type_requested", v)} />
                </div>
              </FormSection>

              <FormSection title="Specifications">
                <div className="grid gap-4 md:grid-cols-3">
                  <InputField
                    label="Budget Amount"
                    value={form.budget_amount}
                    onChange={(v) => updateField("budget_amount", v)}
                    required
                    placeholder="e.g. 50000"
                    errorText={submitAttempted && missingRequiredFieldKeys.has("budget_amount") ? "Budget Amount is required." : undefined}
                  />
                  <InputField label="Currency" value={form.currency} onChange={(v) => updateField("currency", v)} />
                  <InputField
                    label="Quantity"
                    value={form.quantity}
                    onChange={(v) => updateField("quantity", v)}
                    required
                    placeholder="e.g. 100"
                    errorText={submitAttempted && missingRequiredFieldKeys.has("quantity") ? "Quantity is required." : undefined}
                  />
                  <InputField label="Unit of Measure" value={form.unit_of_measure} onChange={(v) => updateField("unit_of_measure", v)} />
                  <InputField
                    label="Required By Date"
                    type="date"
                    value={form.required_by_date}
                    onChange={(v) => updateField("required_by_date", v)}
                    required
                    errorText={submitAttempted && missingRequiredFieldKeys.has("required_by_date") ? "Required By Date is required." : undefined}
                  />
                </div>
              </FormSection>

              <FormSection title="Compliance & Delivery">
                <div className="grid gap-4 md:grid-cols-2">
                  <InputField label="Preferred Supplier" value={form.preferred_supplier_mentioned} onChange={(v) => updateField("preferred_supplier_mentioned", v)} />
                  <InputField label="Delivery Countries" value={form.delivery_countries} onChange={(v) => updateField("delivery_countries", v)} placeholder="e.g. DE, CH, AT" />
                </div>
                <div className="grid gap-3 md:grid-cols-2 mt-2">
                  <SwitchField
                    label="ESG Requirement"
                    description="Environmental, Social & Governance compliance required"
                    checked={form.esg_requirement}
                    onCheckedChange={(v) => updateField("esg_requirement", v)}
                  />
                  <SwitchField
                    label="Data Residency Constraint"
                    description="Data must remain in specific jurisdictions"
                    checked={form.data_residency_constraint}
                    onCheckedChange={(v) => updateField("data_residency_constraint", v)}
                  />
                </div>
              </FormSection>

              <div className="flex justify-between items-center border-t pt-5">
                <Button variant="ghost" onClick={() => setStep(2)} disabled={isSubmitting}>
                  ← Back to Chat
                </Button>
                <div className="flex flex-col items-end gap-2">
                  {missingRequiredFields.length > 0 ? (
                    <p className="text-xs text-amber-700 dark:text-amber-400">
                      {missingRequiredFields.length} required {missingRequiredFields.length === 1 ? "field is" : "fields are"} missing:{" "}
                      {missingRequiredFields.map((field) => field.label).join(", ")}.
                    </p>
                  ) : (
                    <p className="text-xs text-emerald-700 dark:text-emerald-400">
                      All required fields are complete.
                    </p>
                  )}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      onClick={() => submitRequest(false)}
                      disabled={isSubmitting}
                      size="lg"
                      className="min-w-[160px]"
                    >
                      {submitMode === "draft" ? (
                        <>
                          <Loader2 className="mr-2 size-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        "Save as Draft"
                      )}
                    </Button>
                    <Button
                      onClick={() => submitRequest(true)}
                      disabled={isSubmitting || !canSubmit}
                      size="lg"
                      className="min-w-[200px]"
                    >
                      {submitMode === "trigger" ? (
                        <>
                          <Loader2 className="mr-2 size-4 animate-spin" />
                          Submitting...
                        </>
                      ) : (
                        "Submit & Trigger"
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
