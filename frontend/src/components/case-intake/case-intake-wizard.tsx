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
}

export function CaseIntakeWizard() {
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
    setProcessing(true)
    setStep("processing")
    try {
      const extraction = await extractCaseInput({
        sourceType: mode,
        sourceText,
        note,
        requestChannel,
        fileNames: selectedFileNames,
      })
      setResult(extraction)
      const shouldSkipCompletion =
        extraction.extractionStrength === "strong" &&
        computeMissingRequiredFields(extraction.draft).length === 0
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
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Intake"
        title="New Sourcing Case"
        description="Submit messy input first, then review extracted structure before creating the case."
      />

      {loadingCategories ? (
        <Card>
          <CardHeader>
            <CardTitle>Preparing intake</CardTitle>
            <CardDescription>Loading category metadata...</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {step === "processing" ? (
        <Card className="mx-auto max-w-4xl">
          <CardHeader>
            <CardTitle>Processing input</CardTitle>
            <CardDescription>
              Extracting fields, checking completeness, and preparing a structured draft.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert>Analyzing request...</Alert>
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
