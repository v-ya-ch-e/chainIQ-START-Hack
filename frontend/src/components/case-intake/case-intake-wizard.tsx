"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"

import { CompletionStep } from "@/components/case-intake/completion-step"
import { IntakeStep } from "@/components/case-intake/intake-step"
import { ReviewStep } from "@/components/case-intake/review-step"
import { SectionHeading } from "@/components/shared/section-heading"
import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
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
import { cn } from "@/lib/utils"

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
    scenarioTags: [],
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
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [categories, setCategories] = useState<CategoryOption[]>([])
  const [result, setResult] = useState<ExtractionResult>(EMPTY_EXTRACTION)
  const [loadingCategories, setLoadingCategories] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [savingDraft, setSavingDraft] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extractNotice, setExtractNotice] = useState<string | null>(null)
  const [showExtractionPanel, setShowExtractionPanel] = useState(false)

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
  const visibleSteps = [
    { key: "input" as const, title: "Input", description: "Provide source material" },
    { key: "complete" as const, title: "Complete", description: "Fill missing fields" },
    { key: "review" as const, title: "Review", description: "Confirm and create" },
  ]
  const displayedStep =
    step === "created" ? ("review" as const) : step
  const activeStepIndex = visibleSteps.findIndex((entry) => entry.key === displayedStep)

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
      missingRequired: extraction.missingRequired.filter((field) => field !== "categoryId"),
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

  useEffect(() => {
    console.info("[intake-wizard] step changed", {
      step,
      mode,
      processing,
      missingRequiredCount: missingRequired.length,
      extractionStrength: result.extractionStrength,
      fallbackUsed: result.fallbackUsed,
      warningCodes: result.warnings.map((warning) => warning.code),
    })
  }, [
    step,
    mode,
    processing,
    missingRequired.length,
    result.extractionStrength,
    result.fallbackUsed,
    result.warnings,
  ])

  useEffect(() => {
    if (categories.length === 0) return
    setResult((current) => applyCategoryHintMapping(current, categories))
  }, [categories])

  useEffect(() => {
    if (processing) {
      setShowExtractionPanel(true)
      return
    }
    const timeoutId = window.setTimeout(() => {
      setShowExtractionPanel(false)
    }, 240)
    return () => window.clearTimeout(timeoutId)
  }, [processing])

  async function handleExtract() {
    const extractStartedAt = performance.now()
    const effectiveSourceType: IntakeSourceType =
      selectedFiles.length > 0 ? "upload" : "paste"
    console.info("[intake-wizard] extract clicked", {
      mode,
      effectiveSourceType,
      requestChannel,
      sourceTextLength: sourceText.length,
      noteLength: note.length,
      selectedFiles: selectedFiles.map((file) => ({
        name: file.name,
        type: file.type,
        size: file.size,
      })),
      categoryCount: categories.length,
    })
    setError(null)
    setExtractNotice(null)
    if (selectedFiles.length === 0 && sourceText.trim().length === 0) {
      console.warn("[intake-wizard] extract blocked: no source text and no file selected")
      setError("Add a file or paste request text before extracting.")
      return
    }

    setProcessing(true)
    try {
      await new Promise<void>((resolve) => {
        if (typeof window === "undefined") {
          resolve()
          return
        }
        window.requestAnimationFrame(() => resolve())
      })

      console.info("[intake-wizard] starting extraction request")
      const extraction = await extractCaseInput({
        sourceType: effectiveSourceType,
        sourceText,
        note,
        requestChannel,
        files: selectedFiles,
      })
      console.info("[intake-wizard] extraction returned", {
        extractionStrength: extraction.extractionStrength,
        fallbackUsed: extraction.fallbackUsed,
        missingRequiredCount: extraction.missingRequired.length,
        warningCodes: extraction.warnings.map((warning) => warning.code),
        draftPreview: {
          title: extraction.draft.title,
          categoryId: extraction.draft.categoryId,
          currency: extraction.draft.currency,
          budgetAmount: extraction.draft.budgetAmount,
          quantity: extraction.draft.quantity,
          requiredByDate: extraction.draft.requiredByDate,
        },
      })
      const mappedExtraction = applyCategoryHintMapping(extraction, categories)
      console.info("[intake-wizard] extraction after category mapping", {
        categoryId: mappedExtraction.draft.categoryId,
        missingRequiredCount: mappedExtraction.missingRequired.length,
        warningCodes: mappedExtraction.warnings.map((warning) => warning.code),
      })
      setResult(mappedExtraction)
      if (
        mappedExtraction.fallbackUsed ||
        mappedExtraction.warnings.some(
          (warning) =>
            warning.code === "INTAKE_FALLBACK" ||
            warning.code === "UPLOAD_PARSE_FALLBACK" ||
            warning.code === "PARSE_TEXT_FALLBACK",
        )
      ) {
        setExtractNotice(
          "Extraction fallback mode is active. Review all inferred fields before creating the case.",
        )
      }
      const shouldSkipCompletion =
        mappedExtraction.extractionStrength === "strong" &&
        computeMissingRequiredFields(mappedExtraction.draft).length === 0
      console.info("[intake-wizard] extraction finished", {
        shouldSkipCompletion,
        nextStep: shouldSkipCompletion ? "review" : "complete",
        durationMs: Math.round(performance.now() - extractStartedAt),
      })
      setStep(shouldSkipCompletion ? "review" : "complete")
    } catch (extractError) {
      const message =
        extractError instanceof Error
          ? extractError.message
          : "Extraction failed. Please complete fields manually."
      console.error("[intake-wizard] extraction failed", {
        message,
        durationMs: Math.round(performance.now() - extractStartedAt),
        error: extractError,
      })
      setError(message)
      setStep("input")
    } finally {
      console.info("[intake-wizard] extraction cleanup", {
        durationMs: Math.round(performance.now() - extractStartedAt),
      })
      setProcessing(false)
    }
  }

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

  const stageContent =
    step === "input" ? (
      <IntakeStep
        mode={mode}
        sourceText={sourceText}
        note={note}
        requestChannel={requestChannel}
        selectedFiles={selectedFiles}
        processing={processing}
        error={error}
        onModeChange={setMode}
        onSourceTextChange={setSourceText}
        onNoteChange={setNote}
        onRequestChannelChange={setRequestChannel}
        onSelectedFilesChange={setSelectedFiles}
      />
    ) : step === "complete" ? (
      <CompletionStep
        draft={result.draft}
        sourceText={sourceText}
        mode={mode}
        selectedFile={selectedFiles[0] ?? null}
        note={note}
        categories={categories}
        fieldStatus={result.fieldStatus}
        warnings={result.warnings}
        missingRequired={missingRequired}
        onDraftChange={patchDraft}
      />
    ) : step === "review" ? (
      <ReviewStep
        draft={result.draft}
        categories={categories}
        sourceText={sourceText}
        mode={mode}
        selectedFile={selectedFiles[0] ?? null}
        note={note}
        fieldStatus={result.fieldStatus}
        missingRequired={missingRequired}
        warnings={result.warnings}
        error={error}
        onDraftChange={patchDraft}
      />
    ) : (
      <Card className="mx-auto max-w-4xl ring-0 animate-intake-stage-in">
        <CardHeader>
          <CardTitle>Finalizing case</CardTitle>
          <CardDescription>
            Redirecting to the created case and starting the pipeline.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Alert>
            The request was created. The workspace will update automatically once the redirect completes.
          </Alert>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-1/3 animate-intake-progress rounded-full bg-primary/70" />
          </div>
        </CardContent>
      </Card>
    )

  const isInputStep = step === "input"
  const isCompleteStep = step === "complete"
  const isReviewStep = step === "review"
  const canExtract = selectedFiles.length > 0 || sourceText.trim().length > 0
  const canCreate = missingRequired.length === 0

  const footerShellClassName = cn(
    "z-20 flex items-center justify-between gap-3 rounded-[var(--layout-outer-radius)] border border-border/70 bg-background/95 px-[var(--layout-inner-padding)] py-[calc(var(--layout-inner-padding)*0.75)] shadow-none backdrop-blur supports-[backdrop-filter]:bg-background/85 transition-all duration-300",
    embedded ? "shrink-0" : "sticky bottom-0",
  )
  const footerButtonClassName = "min-w-[132px] transition-all duration-200"

  return (
    <div className={embedded ? "flex h-full min-h-0 flex-col gap-[var(--layout-inner-padding)]" : "space-y-6"}>
      {!embedded ? (
        <SectionHeading
          eyebrow="Intake"
          title="New Sourcing Case"
          description="Submit messy input first, then review extracted structure before creating the case."
        />
      ) : null}

      {loadingCategories ? (
        <Card className="ring-0 animate-intake-stage-in">
          <CardHeader>
            <CardTitle>Preparing intake</CardTitle>
            <CardDescription>Loading category metadata...</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/3 animate-intake-progress rounded-full bg-primary/60" />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {extractNotice ? (
        <Alert variant="warning" className="animate-intake-stage-in">
          {extractNotice}
        </Alert>
      ) : null}

      <div className={embedded ? "min-h-0 flex-1 overflow-y-auto pr-1" : ""}>
        <div key={step} className="animate-intake-stage-in">
          {stageContent}
        </div>
      </div>

      <div
        className={cn(
          "overflow-hidden transition-[max-height,opacity] duration-300 ease-out",
          showExtractionPanel ? "max-h-28 opacity-100" : "max-h-0 opacity-0",
        )}
      >
        <div className="rounded-[var(--layout-inner-radius)] border bg-muted/20 px-[var(--layout-inner-padding)] py-[calc(var(--layout-inner-padding)*0.85)]">
          <div className="flex items-center gap-2 text-sm text-foreground">
            <Loader2 className={cn("size-4", processing && "animate-spin")} />
            <span>{processing ? "Extracting structured fields..." : "Extraction complete."}</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full bg-primary/70 transition-[width] duration-300 ease-out",
                processing ? "w-1/3 animate-intake-progress" : "w-full",
              )}
            />
          </div>
        </div>
      </div>

      {step !== "created" ? (
        <div className={footerShellClassName}>
          <div
            key={`footer-${step}`}
            className="flex w-full flex-wrap items-center justify-between gap-2 animate-intake-stage-in"
          >
            <div className="grid w-full grid-cols-3 gap-1.5 md:w-auto md:min-w-[300px]">
              {visibleSteps.map((entry, index) => {
                const isActive = activeStepIndex === index
                const isDone = activeStepIndex > index
                return (
                  <StepChip
                    key={`footer-${entry.key}`}
                    title={`${index + 1}. ${entry.title}`}
                    active={isActive}
                    done={isDone}
                    compact
                  />
                )
              })}
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              {isInputStep ? (
                <Button
                  onClick={handleExtract}
                  disabled={processing || !canExtract}
                  className={footerButtonClassName}
                >
                  {processing ? <Loader2 className="mr-1.5 size-4 animate-spin" /> : null}
                  {processing
                    ? "Extracting..."
                    : selectedFiles.length > 0
                      ? "Analyze file"
                      : "Extract information"}
                </Button>
              ) : null}

              {isCompleteStep ? (
                <>
                  <Button
                    variant="outline"
                    onClick={() => setStep("input")}
                    className={footerButtonClassName}
                  >
                    Back
                  </Button>
                  <Button
                    onClick={() => setStep("review")}
                    className={footerButtonClassName}
                  >
                    Review case
                  </Button>
                </>
              ) : null}

              {isReviewStep ? (
                <>
                  <Button
                    variant="outline"
                    onClick={() => setStep("complete")}
                    className={footerButtonClassName}
                  >
                    Back to edit
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleSaveDraft}
                    disabled={savingDraft || submitting}
                    className={footerButtonClassName}
                  >
                    {savingDraft ? <Loader2 className="mr-1.5 size-4 animate-spin" /> : null}
                    {savingDraft ? "Saving..." : "Save draft"}
                  </Button>
                  <Button
                    onClick={handleCreateCase}
                    disabled={!canCreate || submitting}
                    className={footerButtonClassName}
                  >
                    {submitting ? <Loader2 className="mr-1.5 size-4 animate-spin" /> : null}
                    {submitting ? "Creating..." : "Create case"}
                  </Button>
                </>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function StepChip({
  title,
  active,
  done,
  compact = false,
}: {
  title: string
  active: boolean
  done: boolean
  compact?: boolean
}) {
  return (
    <div
      className={cn(
        "rounded-[var(--layout-inner-radius)] border transition-colors",
        compact ? "px-2 py-1.5 text-xs" : "px-3 py-2 text-sm",
        done && "border-emerald-300 bg-emerald-50 text-emerald-900",
        active && !done ? "border-primary/40 bg-primary/10 text-foreground" : "",
        !active && !done && "bg-background text-muted-foreground",
      )}
    >
      <div className="font-medium">{title}</div>
    </div>
  )
}
