"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { CompletionStep } from "@/components/case-intake/completion-step"
import { IntakeStep } from "@/components/case-intake/intake-step"
import { ReviewStep } from "@/components/case-intake/review-step"
import { SectionHeading } from "@/components/shared/section-heading"
import { Alert } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  computeMissingRequiredFields,
  createCase,
  extractCaseInput,
  getCategoryOptions,
  updateCaseDraft,
} from "@/lib/data/cases"
import type {
  CaseDraftPayload,
  CategoryOption,
  ExtractionResult,
  IntakeFlowStep,
  IntakeSourceType,
  RequestChannel,
} from "@/lib/types/case"

const EMPTY_EXTRACTION: ExtractionResult = {
  draft: {
    title: "",
    requestText: "",
    requestChannel: "portal",
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
    requiredByDate: "",
    deliveryCountries: [],
    preferredSupplierMentioned: null,
    incumbentSupplier: null,
    contractTypeRequested: "one_time",
    dataResidencyConstraint: false,
    esgRequirement: false,
    requesterInstruction: null,
    scenarioTags: ["standard"],
    status: "new",
  },
  fieldStatus: {},
  missingRequired: [],
  warnings: [],
  extractionStrength: "low",
  fallbackUsed: false,
}

interface CaseIntakeWizardProps {
  embedded?: boolean
}

export function CaseIntakeWizard({ embedded = false }: CaseIntakeWizardProps) {
  const router = useRouter()
  const [step, setStep] = useState<IntakeFlowStep>("input")
  const [mode, setMode] = useState<IntakeSourceType>("paste")
  const [sourceText, setSourceText] = useState("")
  const [note, setNote] = useState("")
  const [requestChannel, setRequestChannel] = useState<RequestChannel>("portal")
  const [selectedFileNames, setSelectedFileNames] = useState<string[]>([])
  const [categories, setCategories] = useState<CategoryOption[]>([])
  const [result, setResult] = useState<ExtractionResult>(EMPTY_EXTRACTION)
  const [loadingCategories, setLoadingCategories] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [savingDraft, setSavingDraft] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extractNotice, setExtractNotice] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    setLoadingCategories(true)
    getCategoryOptions()
      .then((items) => {
        if (mounted) {
          setCategories(items)
        }
      })
      .catch(() => {
        if (mounted) {
          setError("Could not load categories. You can still continue with manual values.")
        }
      })
      .finally(() => {
        if (mounted) {
          setLoadingCategories(false)
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  const missingRequired = useMemo(
    () => computeMissingRequiredFields(result.draft),
    [result.draft],
  )
  const stepOrder: IntakeFlowStep[] = ["input", "processing", "complete", "review", "created"]
  const activeStepIndex = stepOrder.indexOf(step)
  const confidenceCount = Object.values(result.fieldStatus).filter(
    (entry) => entry?.status === "confident",
  ).length
  const reviewCount = Object.values(result.fieldStatus).filter(
    (entry) => entry?.status === "inferred" || entry?.status === "needs_review",
  ).length

  function applyCategoryHintMapping(
    extraction: ExtractionResult,
    availableCategories: CategoryOption[],
  ): ExtractionResult {
    if (extraction.draft.categoryId || availableCategories.length === 0) {
      return extraction
    }
    const draftRecord = extraction.draft as unknown as Record<string, unknown>
    const hintedL1 = typeof draftRecord.categoryL1 === "string" ? draftRecord.categoryL1 : null
    const hintedL2 = typeof draftRecord.categoryL2 === "string" ? draftRecord.categoryL2 : null
    if (!hintedL1 || !hintedL2) {
      return extraction
    }
    const matchedCategory = availableCategories.find(
      (category) => category.categoryL1 === hintedL1 && category.categoryL2 === hintedL2,
    )
    if (!matchedCategory) {
      return extraction
    }
    const updatedWarnings = extraction.warnings.filter(
      (warning) => warning.code !== "CATEGORY_MISSING",
    )
    return {
      ...extraction,
      draft: {
        ...extraction.draft,
        categoryId: matchedCategory.id,
      },
      fieldStatus: {
        ...extraction.fieldStatus,
        categoryId: {
          status: "inferred",
          confidence: 0.8,
          reason: "Mapped inferred category hint to known category list.",
        },
      },
      missingRequired:
        extraction.missingRequired.filter((field) => field !== "categoryId"),
      warnings: updatedWarnings,
    }
  }

  function patchDraft(patch: Partial<CaseDraftPayload>) {
    setResult((current) => ({
      ...current,
      draft: {
        ...current.draft,
        ...patch,
      },
    }))
  }

  async function handleExtract() {
    setError(null)
    setExtractNotice(null)
    setProcessing(true)
    setStep("processing")
    try {
      await new Promise<void>((resolve) => {
        if (typeof window === "undefined") {
          resolve()
          return
        }
        window.requestAnimationFrame(() => resolve())
      })
      const extraction = await extractCaseInput({
        sourceType: mode,
        sourceText,
        note,
        requestChannel,
        fileNames: selectedFileNames,
      })
      const mappedExtraction = applyCategoryHintMapping(extraction, categories)
      setResult(mappedExtraction)
      if (
        mappedExtraction.fallbackUsed ||
        mappedExtraction.warnings.some((warning) => warning.code === "INTAKE_FALLBACK")
      ) {
        setExtractNotice(
          "Extraction fallback mode is active. Review all inferred fields before creating the case.",
        )
      }
      const shouldSkipCompletion =
        mappedExtraction.extractionStrength === "strong" &&
        computeMissingRequiredFields(mappedExtraction.draft).length === 0
      setStep(shouldSkipCompletion ? "review" : "complete")
    } catch (extractError) {
      const message =
        extractError instanceof Error
          ? extractError.message
          : "Extraction failed. Please complete fields manually."
      setError(message)
      setStep("complete")
    } finally {
      setProcessing(false)
    }
  }

  useEffect(() => {
    if (categories.length === 0) return
    setResult((current) => applyCategoryHintMapping(current, categories))
  }, [categories])

  async function handleSaveDraft() {
    setError(null)
    setSavingDraft(true)
    try {
      const payload: CaseDraftPayload = {
        ...result.draft,
        status: "new",
      }
      if (payload.requestId) {
        await updateCaseDraft(payload.requestId, payload)
      } else {
        const created = await createCase(payload)
        patchDraft({ requestId: created.requestId })
      }
      setStep("complete")
    } catch (draftError) {
      const message =
        draftError instanceof Error ? draftError.message : "Draft save failed."
      setError(message)
    } finally {
      setSavingDraft(false)
    }
  }

  async function handleCreateCase() {
    setError(null)
    setSubmitting(true)
    try {
      const payload: CaseDraftPayload = {
        ...result.draft,
        status: "submitted",
      }
      const requestId = payload.requestId
        ? (await updateCaseDraft(payload.requestId, payload)).requestId
        : (await createCase(payload)).requestId
      setStep("created")
      router.push(`/cases/${requestId}?tab=overview&created=1`)
    } catch (createError) {
      const message =
        createError instanceof Error ? createError.message : "Case creation failed."
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={embedded ? "space-y-4" : "space-y-6"}>
      {!embedded ? (
        <SectionHeading
          eyebrow="Intake"
          title="New Sourcing Case"
          description="Submit messy input first, then review extracted structure before creating the case."
        />
      ) : null}

      <Card className="border-muted bg-muted/20">
        <CardContent className="space-y-3 pt-4">
          <div className="grid gap-2 md:grid-cols-4">
            <StepChip
              title="1. Input"
              active={activeStepIndex >= 0}
              done={activeStepIndex > 0}
            />
            <StepChip
              title="2. Processing"
              active={step === "processing"}
              done={activeStepIndex > 1}
            />
            <StepChip
              title="3. Complete"
              active={step === "complete"}
              done={activeStepIndex > 2}
            />
            <StepChip
              title="4. Review"
              active={step === "review"}
              done={activeStepIndex > 3}
            />
          </div>
          {step !== "input" ? (
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="rounded-md border bg-background px-2 py-1">
                Confident fields: {confidenceCount}
              </span>
              <span className="rounded-md border bg-background px-2 py-1">
                Need review: {reviewCount}
              </span>
              <span className="rounded-md border bg-background px-2 py-1">
                Missing required: {missingRequired.length}
              </span>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {loadingCategories ? (
        <Card>
          <CardHeader>
            <CardTitle>Preparing intake</CardTitle>
            <CardDescription>Loading category metadata...</CardDescription>
          </CardHeader>
        </Card>
      ) : null}
      {extractNotice ? <Alert variant="warning">{extractNotice}</Alert> : null}

      {step === "processing" ? (
        <Card className="mx-auto max-w-5xl">
          <CardHeader>
            <CardTitle>Processing input</CardTitle>
            <CardDescription>
              Extracting fields, checking completeness, and preparing a structured draft.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Alert>Analyzing request...</Alert>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-primary/60" />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {step === "input" ? (
        <IntakeStep
          mode={mode}
          sourceText={sourceText}
          note={note}
          requestChannel={requestChannel}
          selectedFileNames={selectedFileNames}
          processing={processing}
          error={error}
          onModeChange={setMode}
          onSourceTextChange={setSourceText}
          onNoteChange={setNote}
          onRequestChannelChange={setRequestChannel}
          onSelectedFilesChange={setSelectedFileNames}
          onExtract={handleExtract}
        />
      ) : null}

      {step === "complete" ? (
        <CompletionStep
          draft={result.draft}
          sourceText={sourceText}
          categories={categories}
          fieldStatus={result.fieldStatus}
          warnings={result.warnings}
          missingRequired={missingRequired}
          onDraftChange={patchDraft}
          onBack={() => setStep("input")}
          onContinue={() => setStep("review")}
        />
      ) : null}

      {step === "review" ? (
        <ReviewStep
          draft={result.draft}
          categories={categories}
          sourceText={sourceText}
          fieldStatus={result.fieldStatus}
          missingRequired={missingRequired}
          warnings={result.warnings}
          isSubmitting={submitting}
          isSavingDraft={savingDraft}
          error={error}
          onDraftChange={patchDraft}
          onBackToEdit={() => setStep("complete")}
          onSaveDraft={handleSaveDraft}
          onCreate={handleCreateCase}
        />
      ) : null}
    </div>
  )
}

function StepChip({
  title,
  active,
  done,
}: {
  title: string
  active: boolean
  done: boolean
}) {
  return (
    <div
      className={[
        "rounded-lg border px-3 py-2 text-sm transition-colors",
        done ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "",
        active && !done ? "border-primary/40 bg-primary/10 text-foreground" : "",
        !active ? "bg-background text-muted-foreground" : "",
      ].join(" ")}
    >
      {title}
    </div>
  )
}
