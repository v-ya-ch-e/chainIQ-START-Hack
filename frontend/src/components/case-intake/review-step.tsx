"use client"

import type { ReactNode } from "react"

import { FieldStatusBadge } from "@/components/case-intake/field-status-badge"
import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { CaseDraftPayload, ExtractionWarning, IntakeFieldMeta } from "@/lib/types/case"

interface ReviewStepProps {
  draft: CaseDraftPayload
  sourceText: string
  fieldStatus: Partial<Record<keyof CaseDraftPayload, IntakeFieldMeta>>
  missingRequired: Array<keyof CaseDraftPayload>
  warnings: ExtractionWarning[]
  isSubmitting: boolean
  isSavingDraft: boolean
  error: string | null
  onDraftChange: (patch: Partial<CaseDraftPayload>) => void
  onBackToEdit: () => void
  onCreate: () => void
  onSaveDraft: () => void
}

export function ReviewStep({
  draft,
  sourceText,
  fieldStatus,
  missingRequired,
  warnings,
  isSubmitting,
  isSavingDraft,
  error,
  onDraftChange,
  onBackToEdit,
  onCreate,
  onSaveDraft,
}: ReviewStepProps) {
  const canCreate = missingRequired.length === 0 && !isSubmitting

  return (
    <div className="space-y-4">
      {error ? <Alert variant="destructive">{error}</Alert> : null}
      {warnings.map((warning) => (
        <Alert
          key={warning.code}
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

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
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
              label="Category ID"
              status={fieldStatus.categoryId?.status ?? "needs_review"}
              control={
                <Input
                  inputMode="numeric"
                  value={draft.categoryId ?? ""}
                  onChange={(event) =>
                    onDraftChange({
                      categoryId: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                />
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
                <Input
                  type="date"
                  value={draft.requiredByDate}
                  onChange={(event) =>
                    onDraftChange({ requiredByDate: event.target.value })
                  }
                />
              }
            />

            <div className="space-y-1">
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

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Source reference</CardTitle>
            <CardDescription>
              Compare extracted structure against the original request.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea value={sourceText} readOnly className="min-h-[360px]" />
          </CardContent>
        </Card>
      </div>

      <div className="sticky bottom-2 z-10 flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-card p-3 shadow-sm">
        <Button variant="outline" onClick={onBackToEdit}>
          Back to edit
        </Button>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={onSaveDraft}
            disabled={isSavingDraft || isSubmitting}
          >
            {isSavingDraft ? "Saving..." : "Save draft"}
          </Button>
          <Button onClick={onCreate} disabled={!canCreate}>
            {isSubmitting ? "Creating..." : "Create case"}
          </Button>
        </div>
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
