"use client"

import type { ReactNode } from "react"

import { FieldStatusBadge } from "@/components/case-intake/field-status-badge"
import { SourceReferenceCard } from "@/components/case-intake/source-reference-card"
import { Alert } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { DateMenuInput } from "@/components/ui/date-menu-input"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type {
  CaseDraftPayload,
  CategoryOption,
  ExtractionWarning,
  IntakeFieldMeta,
  IntakeSourceType,
} from "@/lib/types/case"

interface ReviewStepProps {
  draft: CaseDraftPayload
  categories: CategoryOption[]
  sourceText: string
  mode: IntakeSourceType
  selectedFile?: File | null
  note?: string
  fieldStatus: Partial<Record<keyof CaseDraftPayload, IntakeFieldMeta>>
  missingRequired: Array<keyof CaseDraftPayload>
  warnings: ExtractionWarning[]
  error: string | null
  onDraftChange: (patch: Partial<CaseDraftPayload>) => void
}

export function ReviewStep({
  draft,
  categories,
  sourceText,
  mode,
  selectedFile,
  note,
  fieldStatus,
  missingRequired,
  warnings,
  error,
  onDraftChange,
}: ReviewStepProps) {
  const canCreate = missingRequired.length === 0
  const selectedCategoryId = draft.categoryId ? String(draft.categoryId) : ""
  const categoryLabelById = new Map(
    categories.map((category) => [
      String(category.id),
      `${category.categoryL1} / ${category.categoryL2}`,
    ]),
  )
  const selectedCategoryLabel = selectedCategoryId
    ? (categoryLabelById.get(selectedCategoryId) ?? "Unknown category")
    : "Select category"

  return (
    <div className="space-y-4 animate-intake-stage-in">
      {error ? <Alert variant="destructive">{error}</Alert> : null}
      {warnings.map((warning, index) => (
        <Alert
          key={`${warning.code}-${index}`}
          variant={warning.severity === "critical" || warning.severity === "high" ? "destructive" : "warning"}
        >
          {warning.message}
        </Alert>
      ))}
      {missingRequired.length > 0 ? (
        <Alert variant="warning">
          {missingRequired.length} required fields still need completion before case
          creation.
        </Alert>
      ) : null}

      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span className="rounded-full border bg-background px-2.5 py-1">
          Unresolved required {missingRequired.length}
        </span>
        <span className="rounded-full border bg-background px-2.5 py-1">
          Warnings {warnings.length}
        </span>
        <span className="rounded-full border bg-background px-2.5 py-1">
          Ready {canCreate ? "yes" : "no"}
        </span>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
        <Card className="rounded-[var(--layout-inner-radius)] ring-0">
          <CardHeader>
            <CardTitle>Review structured case</CardTitle>
            <CardDescription>
              Final confirmation before creating the case. Key fields remain editable.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <EditableRow
              label="Title"
              status={fieldStatus.title?.status ?? "needs_review"}
              control={
                <Input
                  value={draft.title}
                  onChange={(event) => onDraftChange({ title: event.target.value })}
                />
              }
            />
            <EditableRow
              label="Category"
              status={fieldStatus.categoryId?.status ?? "needs_review"}
              control={
                <Select
                  value={selectedCategoryId}
                  onValueChange={(value) =>
                    onDraftChange({ categoryId: value ? Number(value) : null })
                  }
                >
                  <SelectTrigger className="w-full">
                    <span className="truncate">{selectedCategoryLabel}</span>
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category.id} value={String(category.id)}>
                        {category.categoryL1} / {category.categoryL2}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              }
            />
            <EditableRow
              label="Currency"
              status={fieldStatus.currency?.status ?? "needs_review"}
              control={
                <Input
                  value={draft.currency}
                  onChange={(event) =>
                    onDraftChange({ currency: event.target.value.toUpperCase() })
                  }
                />
              }
            />
            <EditableRow
              label="Budget"
              status={fieldStatus.budgetAmount?.status ?? "needs_review"}
              control={
                <Input
                  inputMode="decimal"
                  value={draft.budgetAmount ?? ""}
                  onChange={(event) =>
                    onDraftChange({
                      budgetAmount: event.target.value
                        ? Number(event.target.value)
                        : null,
                    })
                  }
                />
              }
            />
            <EditableRow
              label="Required by date"
              status={fieldStatus.requiredByDate?.status ?? "needs_review"}
              control={
                <DateMenuInput
                  value={draft.requiredByDate}
                  onChange={(value) => onDraftChange({ requiredByDate: value })}
                />
              }
            />

            <div className="space-y-1 rounded-[var(--layout-inner-radius)] border bg-muted/15 p-[var(--layout-inner-padding)]">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Request text
              </p>
              <Textarea
                value={draft.requestText}
                onChange={(event) => onDraftChange({ requestText: event.target.value })}
              />
            </div>
          </CardContent>
        </Card>

        <SourceReferenceCard
          mode={mode}
          sourceText={sourceText}
          selectedFile={selectedFile}
          note={note}
          sticky
          compact
          title="Source context"
          description="Reference the original request without leaving the review step."
        />
      </div>
    </div>
  )
}

function EditableRow({
  label,
  status,
  control,
}: {
  label: string
  status: "confident" | "inferred" | "missing" | "needs_review"
  control: ReactNode
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <FieldStatusBadge status={status} />
      </div>
      {control}
    </div>
  )
}
