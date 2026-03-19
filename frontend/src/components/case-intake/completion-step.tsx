"use client"

import type { ChangeEvent, ReactNode } from "react"

import { FieldStatusBadge } from "@/components/case-intake/field-status-badge"
import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import type {
  CaseDraftPayload,
  CategoryOption,
  ExtractionWarning,
  IntakeFieldMeta,
  RequestChannel,
} from "@/lib/types/case"

interface CompletionStepProps {
  draft: CaseDraftPayload
  sourceText: string
  categories: CategoryOption[]
  fieldStatus: Partial<Record<keyof CaseDraftPayload, IntakeFieldMeta>>
  warnings: ExtractionWarning[]
  missingRequired: Array<keyof CaseDraftPayload>
  onDraftChange: (patch: Partial<CaseDraftPayload>) => void
  onBack: () => void
  onContinue: () => void
}

function parseNumber(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function statusForField(
  fieldStatus: Partial<Record<keyof CaseDraftPayload, IntakeFieldMeta>>,
  field: keyof CaseDraftPayload,
) {
  return fieldStatus[field]?.status ?? "needs_review"
}

export function CompletionStep({
  draft,
  sourceText,
  categories,
  fieldStatus,
  warnings,
  missingRequired,
  onDraftChange,
  onBack,
  onContinue,
}: CompletionStepProps) {
  const missingSet = new Set(missingRequired)
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
  const requestChannelLabelByValue: Record<RequestChannel, string> = {
    portal: "Portal",
    email: "Email",
    teams: "Teams",
  }

  function handleInput<K extends keyof CaseDraftPayload>(
    key: K,
    value: CaseDraftPayload[K],
  ) {
    onDraftChange({ [key]: value } as Partial<CaseDraftPayload>)
  }

  function parseList(event: ChangeEvent<HTMLInputElement>) {
    return event.target.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  }

  return (
    <div className="space-y-4">
      {warnings.map((warning, index) => (
        <Alert
          key={`${warning.code}-${index}`}
          variant={warning.severity === "critical" || warning.severity === "high" ? "destructive" : "warning"}
        >
          {warning.message}
        </Alert>
      ))}

      <Card className="border-muted bg-muted/20">
        <CardContent className="flex flex-wrap items-center gap-2 pt-4 text-xs text-muted-foreground">
          <span className="rounded-md border bg-background px-2 py-1">
            Filled from extraction: {Object.keys(fieldStatus).length}
          </span>
          <span className="rounded-md border bg-background px-2 py-1">
            Needs completion: {missingRequired.length}
          </span>
          <span className="rounded-md border bg-background px-2 py-1">
            Warnings: {warnings.length}
          </span>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Card className="h-fit xl:sticky xl:top-4">
          <CardHeader>
            <CardTitle>Source input</CardTitle>
            <CardDescription>Keep this visible while you complete fields.</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea value={sourceText} readOnly className="min-h-[420px]" />
          </CardContent>
        </Card>

        <Card className="border-muted">
          <CardHeader>
            <CardTitle>Complete structured case</CardTitle>
            <CardDescription>
              Fill missing values and review inferred fields.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <SectionCard title="Request source">
              <div className="grid gap-3 md:grid-cols-2">
              <FieldLabel label="Title" missing={missingSet.has("title")} status={statusForField(fieldStatus, "title")} />
              <Input
                value={draft.title}
                onChange={(event) => handleInput("title", event.target.value)}
              />

              <FieldLabel
                label="Request channel"
                missing={missingSet.has("requestChannel")}
                status={statusForField(fieldStatus, "requestChannel")}
              />
              <Select
                value={draft.requestChannel}
                onValueChange={(value) =>
                  handleInput("requestChannel", (value as RequestChannel) ?? "portal")
                }
              >
                <SelectTrigger className="w-full">
                  <span className="truncate">
                    {requestChannelLabelByValue[draft.requestChannel] ?? "Portal"}
                  </span>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="portal">Portal</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="teams">Teams</SelectItem>
                </SelectContent>
              </Select>

              <FieldLabel label="Language" missing={missingSet.has("requestLanguage")} status={statusForField(fieldStatus, "requestLanguage")} />
              <Input
                value={draft.requestLanguage}
                onChange={(event) => handleInput("requestLanguage", event.target.value)}
              />

              <FieldLabel label="Business unit" missing={missingSet.has("businessUnit")} status={statusForField(fieldStatus, "businessUnit")} />
              <Input
                value={draft.businessUnit}
                onChange={(event) => handleInput("businessUnit", event.target.value)}
              />

              <FieldLabel label="Country" missing={missingSet.has("country")} status={statusForField(fieldStatus, "country")} />
              <Input
                value={draft.country}
                onChange={(event) => handleInput("country", event.target.value)}
              />

              <FieldLabel label="Site" missing={missingSet.has("site")} status={statusForField(fieldStatus, "site")} />
              <Input
                value={draft.site}
                onChange={(event) => handleInput("site", event.target.value)}
              />

              <FieldLabel label="Requester role" missing={false} status={statusForField(fieldStatus, "requesterRole")} />
              <Input
                value={draft.requesterRole}
                onChange={(event) => handleInput("requesterRole", event.target.value)}
              />

              <FieldLabel label="Requester ID" missing={missingSet.has("requesterId")} status={statusForField(fieldStatus, "requesterId")} />
              <Input
                value={draft.requesterId}
                onChange={(event) => handleInput("requesterId", event.target.value)}
              />

              <FieldLabel label="Submitted for ID" missing={missingSet.has("submittedForId")} status={statusForField(fieldStatus, "submittedForId")} />
              <Input
                value={draft.submittedForId}
                onChange={(event) => handleInput("submittedForId", event.target.value)}
              />

              <div className="md:col-span-2">
                <FieldLabel label="Request text" missing={missingSet.has("requestText")} status={statusForField(fieldStatus, "requestText")} />
                <Textarea
                  value={draft.requestText}
                  onChange={(event) => handleInput("requestText", event.target.value)}
                />
              </div>
              </div>
            </SectionCard>

            <Separator />
            <SectionCard title="Sourcing requirements">
              <div className="grid gap-3 md:grid-cols-2">
              <FieldLabel label="Category" missing={missingSet.has("categoryId")} status={statusForField(fieldStatus, "categoryId")} />
              <Select
                value={selectedCategoryId}
                onValueChange={(value) => handleInput("categoryId", value ? Number(value) : null)}
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

              <FieldLabel label="Quantity" missing={false} status={statusForField(fieldStatus, "quantity")} />
              <Input
                inputMode="decimal"
                value={draft.quantity ?? ""}
                onChange={(event) => handleInput("quantity", parseNumber(event.target.value))}
              />

              <FieldLabel label="Unit of measure" missing={missingSet.has("unitOfMeasure")} status={statusForField(fieldStatus, "unitOfMeasure")} />
              <Input
                value={draft.unitOfMeasure}
                onChange={(event) => handleInput("unitOfMeasure", event.target.value)}
              />

              <FieldLabel label="Currency" missing={missingSet.has("currency")} status={statusForField(fieldStatus, "currency")} />
              <Input
                value={draft.currency}
                onChange={(event) => handleInput("currency", event.target.value.toUpperCase())}
              />

              <FieldLabel label="Budget amount" missing={false} status={statusForField(fieldStatus, "budgetAmount")} />
              <Input
                inputMode="decimal"
                value={draft.budgetAmount ?? ""}
                onChange={(event) =>
                  handleInput("budgetAmount", parseNumber(event.target.value))
                }
              />

              <FieldLabel label="Required by date" missing={missingSet.has("requiredByDate")} status={statusForField(fieldStatus, "requiredByDate")} />
              <Input
                type="date"
                value={draft.requiredByDate}
                onChange={(event) => handleInput("requiredByDate", event.target.value)}
              />

              <FieldLabel label="Delivery countries (comma separated)" missing={false} status={statusForField(fieldStatus, "deliveryCountries")} />
              <Input
                value={draft.deliveryCountries.join(", ")}
                onChange={(event) =>
                  handleInput("deliveryCountries", parseList(event))
                }
              />

              <FieldLabel label="Contract type" missing={missingSet.has("contractTypeRequested")} status={statusForField(fieldStatus, "contractTypeRequested")} />
              <Input
                value={draft.contractTypeRequested}
                onChange={(event) =>
                  handleInput("contractTypeRequested", event.target.value)
                }
              />
              </div>
            </SectionCard>

            <Separator />
            <SectionCard title="Constraints & preferences">
              <div className="grid gap-3 md:grid-cols-2">
              <FieldLabel label="Preferred supplier" missing={false} status={statusForField(fieldStatus, "preferredSupplierMentioned")} />
              <Input
                value={draft.preferredSupplierMentioned ?? ""}
                onChange={(event) =>
                  handleInput(
                    "preferredSupplierMentioned",
                    event.target.value.trim() || null,
                  )
                }
              />

              <FieldLabel label="Incumbent supplier" missing={false} status={statusForField(fieldStatus, "incumbentSupplier")} />
              <Input
                value={draft.incumbentSupplier ?? ""}
                onChange={(event) =>
                  handleInput("incumbentSupplier", event.target.value.trim() || null)
                }
              />

              <div className="md:col-span-2 space-y-2">
                <FieldLabel label="Requester instruction" missing={false} status={statusForField(fieldStatus, "requesterInstruction")} />
                <Textarea
                  value={draft.requesterInstruction ?? ""}
                  onChange={(event) =>
                    handleInput("requesterInstruction", event.target.value || null)
                  }
                />
              </div>

              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={draft.dataResidencyConstraint}
                  onCheckedChange={(checked) =>
                    handleInput("dataResidencyConstraint", checked === true)
                  }
                />
                Data residency constraint
              </label>

              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={draft.esgRequirement}
                  onCheckedChange={(checked) =>
                    handleInput("esgRequirement", checked === true)
                  }
                />
                ESG requirement
              </label>
              </div>
            </SectionCard>
          </CardContent>
        </Card>
      </div>

      <div className="sticky bottom-0 z-10 flex items-center justify-between rounded-lg border bg-card/95 p-3 backdrop-blur-sm">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onContinue}>Review case</Button>
      </div>
    </div>
  )
}

function SectionTitle({ title }: { title: string }) {
  return (
    <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
      {title}
    </p>
  )
}

function SectionCard({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="space-y-3 rounded-lg border bg-muted/15 p-3">
      <SectionTitle title={title} />
      {children}
    </div>
  )
}

function FieldLabel({
  label,
  missing,
  status,
}: {
  label: string
  missing: boolean
  status: "confident" | "inferred" | "missing" | "needs_review"
}) {
  return (
    <div className="mt-0.5 flex items-center justify-between gap-2 text-xs">
      <span className={missing ? "font-medium text-destructive" : "text-muted-foreground"}>
        {missing ? `${label} *` : label}
      </span>
      <FieldStatusBadge status={status} />
    </div>
  )
}
