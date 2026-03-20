"use client"

import Link from "next/link"
import { ArrowRight, Loader2, Plus, Search } from "lucide-react"
import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react"

import {
  TopbarFilters,
  topbarFilterControlClassName,
} from "@/components/app-shell/topbar-filters"
import { useSetWorkspaceHeaderActions } from "@/components/app-shell/workspace-header-actions"
import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import {
  displayRecommendationStatus,
  formatCountryDisplayName,
  formatDateTime,
} from "@/lib/data/formatters"
import { labelForFilterValue, type FilterOption } from "@/lib/filter-options"
import type { QueueEscalationItem } from "@/lib/types/case"
import type { DynamicRuleCreate } from "@/lib/api/types"
import { cn } from "@/lib/utils"
import { chainIqApi } from "@/lib/api/client"

interface EscalationsPageProps {
  items: QueueEscalationItem[]
}

const escalationStatusOptions: FilterOption[] = [
  { value: "all", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "resolved", label: "Resolved" },
]

const escalationTypeOptions: FilterOption[] = [
  { value: "all", label: "All types" },
  { value: "blocking", label: "Blocking only" },
  { value: "advisory", label: "Advisory only" },
]

const EscalationsWorkspaceToolbar = memo(function EscalationsWorkspaceToolbar({
  query,
  statusFilter,
  blockingFilter,
  onQueryChange,
  onStatusChange,
  onBlockingChange,
  onNewRule,
}: {
  query: string
  statusFilter: string
  blockingFilter: string
  onQueryChange: (value: string) => void
  onStatusChange: (value: string | null) => void
  onBlockingChange: (value: string | null) => void
  onNewRule: () => void
}) {
  const statusTriggerLabel = labelForFilterValue(
    escalationStatusOptions,
    statusFilter,
    "All statuses",
  )
  const blockingTriggerLabel = labelForFilterValue(
    escalationTypeOptions,
    blockingFilter,
    "All types",
  )

  return (
    <TopbarFilters>
      <div className="relative h-8 min-w-[14rem] grow basis-full sm:basis-auto sm:max-w-[24rem] sm:grow">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search case, rule, target role, business unit…"
          className={cn(
            "h-8 border-input/80 pl-8 text-sm transition-colors focus-visible:border-ring",
            topbarFilterControlClassName,
          )}
        />
      </div>

      <Select value={statusFilter} onValueChange={onStatusChange}>
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[10.5rem] grow transition-[color,box-shadow,opacity] duration-150 sm:max-w-[12rem] sm:grow-0",
            topbarFilterControlClassName,
          )}
        >
          <span className="truncate text-left" data-slot="select-value">
            {statusTriggerLabel}
          </span>
        </SelectTrigger>
        <SelectContent>
          {escalationStatusOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={blockingFilter} onValueChange={onBlockingChange}>
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[10.5rem] grow transition-[color,box-shadow,opacity] duration-150 sm:max-w-[12rem] sm:grow-0",
            topbarFilterControlClassName,
          )}
        >
          <span className="truncate text-left" data-slot="select-value">
            {blockingTriggerLabel}
          </span>
        </SelectTrigger>
        <SelectContent>
          {escalationTypeOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        size="sm"
        className={cn("h-8 shrink-0", topbarFilterControlClassName)}
        onClick={onNewRule}
      >
        <Plus className="mr-1.5 size-4" />
        New Rule
      </Button>
    </TopbarFilters>
  )
})

export function EscalationsPage({ items }: EscalationsPageProps) {
  const openCount = items.filter((item) => item.status !== "resolved").length
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [blockingFilter, setBlockingFilter] = useState("all")
  const setHeaderActions = useSetWorkspaceHeaderActions()
  const [selectedEscalationId, setSelectedEscalationId] = useState<string | null>(null)
  const [isReviewOpen, setIsReviewOpen] = useState(false)
  const [ruleDetails, setRuleDetails] = useState<Record<string, unknown> | null>(null)
  const [auditSummary, setAuditSummary] = useState<Record<string, unknown> | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<Record<string, unknown> | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false)

  const openNewRuleDialog = useCallback(() => setRuleDialogOpen(true), [])

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()

    return items.filter((item) => {
      const matchesQuery =
        !normalizedQuery ||
        item.caseId.toLowerCase().includes(normalizedQuery) ||
        item.title.toLowerCase().includes(normalizedQuery) ||
        item.ruleId.toLowerCase().includes(normalizedQuery) ||
        item.ruleLabel.toLowerCase().includes(normalizedQuery) ||
        item.escalateTo.toLowerCase().includes(normalizedQuery) ||
        item.businessUnit.toLowerCase().includes(normalizedQuery) ||
        item.country.toLowerCase().includes(normalizedQuery)

      const matchesStatus =
        statusFilter === "all" ? true : item.status === statusFilter

      const matchesBlocking =
        blockingFilter === "all"
          ? true
          : blockingFilter === "blocking"
            ? item.blocking
            : !item.blocking

      return matchesQuery && matchesStatus && matchesBlocking
    })
  }, [blockingFilter, items, query, statusFilter])

  const handleStatusFilterChange = useCallback((value: string | null) => {
    setStatusFilter(value ?? "all")
  }, [])

  const handleBlockingFilterChange = useCallback((value: string | null) => {
    setBlockingFilter(value ?? "all")
  }, [])

  const selectedItem =
    filteredItems.find((item) => item.escalationId === selectedEscalationId) ??
    items.find((item) => item.escalationId === selectedEscalationId) ??
    null

  function openReview(item: QueueEscalationItem) {
    setSelectedEscalationId(item.escalationId)
    setIsReviewOpen(true)
  }

  useEffect(() => {
    let active = true
    async function hydrateReviewState() {
      if (!selectedItem || !isReviewOpen) {
        return
      }
      try {
        setReviewLoading(true)
        setReviewError(null)
        const [rule, summary, status] = await Promise.all([
          chainIqApi.rules.escalationById(selectedItem.ruleId),
          chainIqApi.pipeline
            .auditSummary(selectedItem.caseId)
            .catch(() => null),
          chainIqApi.pipeline.status(selectedItem.caseId).catch(() => null),
        ])
        if (!active) return
        setRuleDetails((rule as unknown as Record<string, unknown>) ?? null)
        setAuditSummary((summary as unknown as Record<string, unknown>) ?? null)
        setPipelineStatus((status as Record<string, unknown>) ?? null)
      } catch (error) {
        if (!active) return
        setReviewError(
          error instanceof Error
            ? error.message
            : "Failed to load related escalation context.",
        )
      } finally {
        if (active) {
          setReviewLoading(false)
        }
      }
    }
    hydrateReviewState()
    return () => {
      active = false
    }
  }, [isReviewOpen, selectedItem])

  useLayoutEffect(
    () => {
      setHeaderActions(
        <EscalationsWorkspaceToolbar
          query={query}
          statusFilter={statusFilter}
          blockingFilter={blockingFilter}
          onQueryChange={setQuery}
          onStatusChange={handleStatusFilterChange}
          onBlockingChange={handleBlockingFilterChange}
          onNewRule={openNewRuleDialog}
        />,
      )
      return () => setHeaderActions(null)
    },
    [
      setHeaderActions,
      query,
      statusFilter,
      blockingFilter,
      handleStatusFilterChange,
      handleBlockingFilterChange,
      openNewRuleDialog,
    ],
  )

  return (
    <>
      <div className="space-y-6">
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Escalations"
          title={`${openCount} open reviews`}
          description="Human-review queue for blocked or conditionally proceedable cases."
        />
      </div>

        <div
          className="animate-fade-in-up grid gap-3 @xl/main:grid-cols-3"
          style={{ animationDelay: "80ms" }}
        >
          <QueueMetric
            label="Open escalations"
            value={openCount.toString()}
            helper="Awaiting human decision"
          />
          <QueueMetric
            label="Blocking cases"
            value={items
              .filter((item) => item.blocking && item.status !== "resolved")
              .length.toString()}
            helper="Cannot proceed autonomously"
          />
          <QueueMetric
            label="Target roles"
            value={new Set(items.map((item) => item.escalateTo)).size.toString()}
            helper="Distinct stakeholders involved"
          />
        </div>

      <Card className="animate-fade-in-up" style={{ animationDelay: "160ms" }}>
        <CardHeader className="space-y-2 border-b pb-4">
          <CardTitle>All escalations</CardTitle>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>
              Showing {filteredItems.length} of {items.length} escalations
            </span>
            {statusFilter !== "all" ? (
              <StatusBadge
                label={labelForFilterValue(
                  escalationStatusOptions,
                  statusFilter,
                  "Status",
                )}
                tone="info"
              />
            ) : null}
            {blockingFilter !== "all" ? (
              <StatusBadge
                label={labelForFilterValue(
                  escalationTypeOptions,
                  blockingFilter,
                  "Type",
                )}
                tone="warning"
              />
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[220px] px-4">Case</TableHead>
                  <TableHead className="min-w-[120px]">Rule</TableHead>
                  <TableHead className="min-w-[140px]">Escalate To</TableHead>
                  <TableHead className="min-w-[90px]">Blocking</TableHead>
                  <TableHead className="min-w-[90px]">Status</TableHead>
                  <TableHead className="min-w-[130px]">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No escalations match the current filters.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredItems.map((item) => (
                    <TableRow
                      key={item.escalationId}
                      data-state={
                        selectedEscalationId === item.escalationId ? "selected" : undefined
                      }
                      className="group cursor-pointer"
                      tabIndex={0}
                      role="button"
                      aria-label={`Review escalation ${item.escalationId}`}
                      onClick={() => openReview(item)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault()
                          openReview(item)
                        }
                      }}
                    >
                      <TableCell className="px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-medium">{item.title}</p>
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                              {item.category} · {formatCountryDisplayName(item.country)}
                            </p>
                          </div>
                          <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                        </div>
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={item.ruleLabel?.trim() || item.ruleId}
                          tone="info"
                        />
                      </TableCell>
                      <TableCell className="text-sm">
                        {item.escalateTo}
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={item.blocking ? "blocking" : "advisory"}
                          tone={item.blocking ? "destructive" : "warning"}
                        />
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={item.status}
                          tone={
                            item.status === "resolved"
                              ? "success"
                              : "neutral"
                          }
                        />
                      </TableCell>
                      <TableCell className="text-sm tabular-nums" suppressHydrationWarning>
                        {formatDateTime(item.createdAt)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      </div>

      <Sheet open={isReviewOpen} onOpenChange={setIsReviewOpen}>
        <SheetContent
          side="right"
          className="data-[side=right]:w-full data-[side=right]:sm:max-w-4xl bg-white shadow-2xl"
        >
          <SheetHeader>
            <SheetTitle>
              {selectedItem ? `Review: ${selectedItem.title}` : "Review escalation"}
            </SheetTitle>
            <SheetDescription>
              Human review workspace for escalation triage and case handoff.
            </SheetDescription>
          </SheetHeader>

          {selectedItem ? (
            <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pb-4">
              <div className="rounded-lg border p-3">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Request snapshot
                </p>
                <p className="mt-1 text-sm font-semibold">{selectedItem.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {selectedItem.caseId} · {selectedItem.businessUnit}
                </p>
                <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <DetailRow label="Category" value={selectedItem.category} />
                  <DetailRow
                    label="Business unit"
                    value={selectedItem.businessUnit}
                  />
                  <DetailRow
                    label="Country"
                    value={formatCountryDisplayName(selectedItem.country)}
                  />
                  <DetailRow
                    label="Created"
                    value={formatDateTime(selectedItem.createdAt)}
                  />
                </div>
              </div>

              <div className="rounded-lg border p-3">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Escalation context
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <StatusBadge label={selectedItem.ruleId} tone="info" />
                  <StatusBadge
                    label={selectedItem.blocking ? "blocking" : "advisory"}
                    tone={selectedItem.blocking ? "destructive" : "warning"}
                  />
                  <StatusBadge
                    label={selectedItem.status}
                    tone={
                      selectedItem.status === "resolved"
                        ? "success"
                        : "neutral"
                    }
                  />
                </div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {selectedItem.ruleLabel}
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {selectedItem.trigger}
                </p>
                <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <DetailRow label="Escalate to" value={selectedItem.escalateTo} />
                  <DetailRow
                    label="Recommendation state"
                    value={displayRecommendationStatus(selectedItem.recommendationStatus)}
                  />
                  <DetailRow
                    label="Suggested next action"
                    value={
                      selectedItem.blocking
                        ? `Coordinate decision with ${selectedItem.escalateTo}`
                        : `Document advisory input from ${selectedItem.escalateTo}`
                    }
                  />
                  <DetailRow
                    label="Last updated"
                    value={formatDateTime(selectedItem.lastUpdated)}
                  />
                </div>
              </div>

              <div className="rounded-lg border p-3">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Related rule and runtime context
                </p>
                {reviewLoading ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Loading additional context...
                  </p>
                ) : null}
                {reviewError ? (
                  <p className="mt-2 text-sm text-rose-700">{reviewError}</p>
                ) : null}
                <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <DetailRow
                    label="Rule action"
                    value={String(ruleDetails?.action ?? "Not available")}
                  />
                  <DetailRow
                    label="Rule trigger condition"
                    value={String(
                      ruleDetails?.trigger_condition ?? "Not available",
                    )}
                  />
                  <DetailRow
                    label="Audit entries"
                    value={String(auditSummary?.total_entries ?? "N/A")}
                  />
                  <DetailRow
                    label="Escalations in audit"
                    value={String(auditSummary?.escalation_count ?? "N/A")}
                  />
                  <DetailRow
                    label="Pipeline status"
                    value={String(pipelineStatus?.status ?? "Unavailable")}
                  />
                  <DetailRow
                    label="Pipeline run"
                    value={String(pipelineStatus?.run_id ?? "Unavailable")}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="px-4 py-2 text-sm text-muted-foreground">
              Select an escalation row to review details.
            </div>
          )}

          <SheetFooter className="border-t pt-3">
            {selectedItem ? (
              <>
                <Link
                  href={`/cases/${selectedItem.caseId}`}
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                >
                  Open full case
                </Link>
                <Link
                  href={`/cases/${selectedItem.caseId}?tab=escalations`}
                  className={cn(buttonVariants({ size: "sm" }))}
                >
                  Start review
                </Link>
              </>
            ) : null}
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Dialog open={ruleDialogOpen} onOpenChange={setRuleDialogOpen}>
        <DialogContent className="w-[min(100vw-2rem,56rem)] max-w-none p-0" showCloseButton={false}>
          <DialogHeader className="border-b px-5 py-4">
            <DialogTitle>New Rule</DialogTitle>
            <DialogDescription>
              Describe a new rule or a change to an existing one in plain text.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="max-h-[calc(100svh-9rem)] overflow-y-auto p-5">
            {ruleDialogOpen ? (
              <RuleWizard onClose={() => setRuleDialogOpen(false)} />
            ) : null}
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  )
}

type RuleWizardStep = "input" | "review"

function RuleWizard({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState<RuleWizardStep>("input")
  const [text, setText] = useState("")
  const [generatedRule, setGeneratedRule] = useState<DynamicRuleCreate | null>(null)
  const [isUpdate, setIsUpdate] = useState(false)
  const [targetRuleId, setTargetRuleId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function handleGenerate() {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    try {
      const result = await chainIqApi.dynamicRules.parse({ text: text.trim() })
      setGeneratedRule(result.rule)
      setIsUpdate(result.is_update)
      setTargetRuleId(result.target_rule_id)
      setStep("review")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate rule")
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!generatedRule) return
    setSaving(true)
    setError(null)
    try {
      if (isUpdate && targetRuleId) {
        const { rule_id: _id, created_by: _cb, ...fields } = generatedRule
        await chainIqApi.dynamicRules.update(targetRuleId, {
          ...fields,
          changed_by: "user",
          change_reason: text.trim(),
        })
        setSuccess(`Rule ${targetRuleId} updated successfully.`)
      } else {
        await chainIqApi.dynamicRules.create({
          ...generatedRule,
          created_by: "user",
        })
        setSuccess(`Rule ${generatedRule.rule_id} created successfully.`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save rule")
    } finally {
      setSaving(false)
    }
  }

  if (success) {
    return (
      <div className="space-y-4 text-center">
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-medium text-emerald-800">{success}</p>
        </div>
        <Button variant="outline" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>
    )
  }

  if (step === "input") {
    return (
      <div className="space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="rule-text" className="text-sm font-medium">
            Describe what you need
          </label>
          <Textarea
            id="rule-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              "e.g. Exclude suppliers with ESG score below 40\n" +
              "e.g. Change the risk score threshold from 70 to 50\n" +
              "e.g. Add an escalation when budget exceeds 1 million EUR"
            }
            rows={5}
            className="resize-none"
          />
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleGenerate} disabled={loading || !text.trim()}>
            {loading ? (
              <>
                <Loader2 className="mr-1.5 size-4 animate-spin" />
                Generating...
              </>
            ) : (
              "Generate"
            )}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {isUpdate ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
          <p className="text-sm text-amber-800">
            This will <strong>update</strong> existing rule <strong>{targetRuleId}</strong>
          </p>
        </div>
      ) : (
        <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2">
          <p className="text-sm text-blue-800">
            This will <strong>create</strong> a new rule <strong>{generatedRule?.rule_id}</strong>
          </p>
        </div>
      )}

      {generatedRule ? <RulePreview rule={generatedRule} /> : null}

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setStep("input")
            setGeneratedRule(null)
            setError(null)
          }}
        >
          Back
        </Button>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? (
            <>
              <Loader2 className="mr-1.5 size-4 animate-spin" />
              Saving...
            </>
          ) : isUpdate ? (
            "Apply Update"
          ) : (
            "Create Rule"
          )}
        </Button>
      </div>
    </div>
  )
}

const severityTone: Record<string, "destructive" | "warning" | "neutral"> = {
  critical: "destructive",
  high: "warning",
  medium: "neutral",
  low: "neutral",
}

function RulePreview({ rule }: { rule: DynamicRuleCreate }) {
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <p className="text-lg font-semibold">{rule.rule_name}</p>
        <p className="text-xs text-muted-foreground">{rule.rule_id}</p>
      </div>

      {rule.description ? (
        <p className="text-sm leading-relaxed text-muted-foreground">{rule.description}</p>
      ) : null}

      <div className="flex flex-wrap gap-1.5">
        <StatusBadge label={rule.rule_category} tone="info" />
        <StatusBadge label={rule.eval_type} tone="info" />
        <StatusBadge label={`scope: ${rule.scope ?? "request"}`} tone="neutral" />
        <StatusBadge label={`stage: ${rule.pipeline_stage}`} tone="neutral" />
        <StatusBadge
          label={rule.severity ?? "medium"}
          tone={severityTone[rule.severity ?? "medium"] ?? "neutral"}
        />
        {rule.is_blocking ? <StatusBadge label="blocking" tone="destructive" /> : null}
      </div>

      <div className="grid gap-2 text-sm sm:grid-cols-2">
        <DetailRow label="Action on fail" value={rule.action_on_fail ?? "warn"} />
        <DetailRow label="Priority" value={String(rule.priority ?? 100)} />
        {rule.escalation_target ? (
          <DetailRow label="Escalation target" value={rule.escalation_target} />
        ) : null}
        {rule.fail_message_template ? (
          <DetailRow label="Fail message" value={rule.fail_message_template} />
        ) : null}
      </div>

      <details className="group">
        <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
          eval_config (JSON)
        </summary>
        <pre className="mt-2 overflow-x-auto rounded-md bg-muted/50 p-3 text-xs leading-relaxed">
          {JSON.stringify(rule.eval_config, null, 2)}
        </pre>
      </details>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/20 p-2.5">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm">{value}</p>
    </div>
  )
}

function QueueMetric({
  label,
  value,
  helper,
}: {
  label: string
  value: string
  helper: string
}) {
  return (
    <Card>
      <CardContent className="space-y-1.5 px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className="text-2xl font-semibold tabular-nums tracking-tight">
          {value}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {helper}
        </p>
      </CardContent>
    </Card>
  )
}
