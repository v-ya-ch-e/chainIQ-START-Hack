"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import {
  memo,
  useCallback,
  useDeferredValue,
  useLayoutEffect,
  useMemo,
  useState,
  useTransition,
} from "react"
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Play,
  Plus,
  Search,
} from "lucide-react"

import {
  TopbarFilters,
  topbarFilterControlClassName,
} from "@/components/app-shell/topbar-filters"
import { useSetWorkspaceHeaderActions } from "@/components/app-shell/workspace-header-actions"
import { StatusBadge } from "@/components/shared/status-badge"
import { CaseIntakeWizard } from "@/components/case-intake/case-intake-wizard"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  displayCaseStatus,
  displayRecommendationStatus,
  formatCountryDisplayName,
  formatCurrency,
  formatDate,
  formatDateTime,
  titleCase,
} from "@/lib/data/formatters"
import { chainIqApi } from "@/lib/api/client"
import { usePipelineActionRunner } from "@/lib/pipeline/action-runner"
import {
  type PipelineLivePhase,
  useRequestStatusPoller,
} from "@/lib/pipeline/request-status-poller"
import type { CaseListItem } from "@/lib/types/case"
import { labelForFilterValue, type FilterOption } from "@/lib/filter-options"
import { cn } from "@/lib/utils"

interface InboxPageProps {
  cases: CaseListItem[]
  total: number
  page: number
  pageSize: number
  statusParam: string
  dataLoadError?: string | null
}

const statusOptions: FilterOption[] = [
  { value: "all", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "submitted", label: "Submitted" },
  { value: "pending_review", label: "Pending review" },
  { value: "evaluated", label: "Evaluated" },
  { value: "recommended", label: "Recommended" },
  { value: "escalated", label: "Escalated" },
  { value: "resolved", label: "Resolved" },
]

const escalationOptions: FilterOption[] = [
  { value: "all", label: "All escalations" },
  { value: "none", label: "No escalation" },
  { value: "advisory", label: "Advisory" },
  { value: "blocking", label: "Blocking" },
]

function displayEscalationStatus(raw: string) {
  const match = escalationOptions.find((o) => o.value === raw && o.value !== "all")
  return match?.label ?? titleCase(raw)
}

function labelForLivePhase(phase: PipelineLivePhase) {
  switch (phase) {
    case "idle":
      return "Not started"
    case "queued":
      return "Queued"
    case "running":
      return "Running"
    case "completed":
      return "Completed"
    case "failed":
      return "Failed"
    case "timed_out":
      return "Timed out"
    default:
      return "Unknown"
  }
}

function toneForLivePhase(phase: PipelineLivePhase) {
  switch (phase) {
    case "completed":
      return "success" as const
    case "failed":
    case "timed_out":
      return "destructive" as const
    case "running":
      return "info" as const
    case "queued":
      return "warning" as const
    case "idle":
      return "neutral" as const
    default:
      return "neutral" as const
  }
}

function emptyCell() {
  return <span className="text-muted-foreground">—</span>
}

const InboxWorkspaceToolbar = memo(function InboxWorkspaceToolbar({
  query,
  onQueryChange,
  statusValue,
  onStatusChange,
  escalationFilter,
  onEscalationChange,
  attentionOnly,
  onAttentionChange,
  onNewRequest,
}: {
  query: string
  onQueryChange: (value: string) => void
  statusValue: string
  onStatusChange: (value: string | null) => void
  escalationFilter: string
  onEscalationChange: (value: string | null) => void
  attentionOnly: boolean
  onAttentionChange: (checked: boolean) => void
  onNewRequest: () => void
}) {
  const statusTriggerLabel = labelForFilterValue(
    statusOptions,
    statusValue,
    "All statuses",
  )
  const escalationTriggerLabel = labelForFilterValue(
    escalationOptions,
    escalationFilter,
    "All escalations",
  )

  return (
    <TopbarFilters>
      <div className="relative h-8 min-w-[14rem] grow basis-full sm:basis-auto sm:max-w-[22rem] sm:grow">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Filter by request, title, supplier, unit, country…"
          className={cn(
            "h-8 border-input/80 pl-8 text-sm transition-colors focus-visible:border-ring",
            topbarFilterControlClassName,
          )}
        />
      </div>
      <Select value={statusValue} onValueChange={onStatusChange}>
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
          {statusOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={escalationFilter}
        onValueChange={onEscalationChange}
      >
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[10.5rem] grow transition-[color,box-shadow,opacity] duration-150 sm:max-w-[12rem] sm:grow-0",
            topbarFilterControlClassName,
          )}
        >
          <span className="truncate text-left" data-slot="select-value">
            {escalationTriggerLabel}
          </span>
        </SelectTrigger>
        <SelectContent>
          {escalationOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <label
        className={cn(
          "flex h-8 shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap border border-transparent bg-transparent px-2.5 text-xs text-muted-foreground transition-colors hover:text-foreground",
          topbarFilterControlClassName,
        )}
      >
        <Checkbox
          checked={attentionOnly}
          onCheckedChange={(checked) => onAttentionChange(checked === true)}
        />
        Needs attention only
      </label>
      <Button
        size="sm"
        className={cn("h-8 shrink-0", topbarFilterControlClassName)}
        onClick={onNewRequest}
      >
        <Plus className="mr-1.5 size-4" />
        New Request
      </Button>
    </TopbarFilters>
  )
})

export function InboxPage({
  cases,
  total,
  page,
  pageSize,
  statusParam,
  dataLoadError,
}: InboxPageProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [query, setQuery] = useState("")
  const [escalationFilter, setEscalationFilter] = useState("all")
  const [newRequestOpen, setNewRequestOpen] = useState(false)
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [isFilterNavPending, startFilterTransition] = useTransition()
  const deferredQuery = useDeferredValue(query)
  const {
    requestLiveState,
    startPolling,
    patchRequestState,
    clearRequestState,
  } = useRequestStatusPoller()
  const { loadingAction, runAction } =
    usePipelineActionRunner()

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const updateSearchParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      startFilterTransition(() => {
        const params = new URLSearchParams(searchParams.toString())
        for (const [key, value] of Object.entries(updates)) {
          if (value === undefined || value === "all") {
            params.delete(key)
          } else {
            params.set(key, value)
          }
        }
        const qs = params.toString()
        const href = `/inbox${qs ? `?${qs}` : ""}`
        router.replace(href, { scroll: false })
      })
    },
    [router, searchParams, startFilterTransition],
  )

  const handleStatusChange = useCallback(
    (value: string | null) => {
      const v = value ?? "all"
      updateSearchParams({ status: v === "all" ? undefined : v, page: undefined })
    },
    [updateSearchParams],
  )

  const handleEscalationFilterChange = useCallback((value: string | null) => {
    setEscalationFilter(value ?? "all")
  }, [])

  const openNewRequest = useCallback(() => {
    setNewRequestOpen(true)
  }, [])

  function handlePageChange(newPage: number) {
    updateSearchParams({ page: newPage <= 1 ? undefined : String(newPage) })
  }

  const filteredCases = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase()
    return cases.filter((entry) => {
      const matchesQuery =
        !normalizedQuery ||
        entry.requestId.toLowerCase().includes(normalizedQuery) ||
        entry.title.toLowerCase().includes(normalizedQuery) ||
        entry.businessUnit.toLowerCase().includes(normalizedQuery) ||
        entry.countryLabel.toLowerCase().includes(normalizedQuery) ||
        entry.supplierLabel.toLowerCase().includes(normalizedQuery)

      const matchesEscalation =
        escalationFilter === "all"
          ? true
          : entry.escalationStatus === escalationFilter

      const matchesAttention = attentionOnly ? entry.needsAttention : true

      return matchesQuery && matchesEscalation && matchesAttention
    })
  }, [attentionOnly, cases, deferredQuery, escalationFilter])

  const isSearchDeferring = query !== deferredQuery

  const statusValue = useMemo(
    () =>
      statusOptions.some((option) => option.value === statusParam)
        ? statusParam
        : "all",
    [statusParam],
  )

  const setHeaderActions = useSetWorkspaceHeaderActions()

  useLayoutEffect(
    () => {
      setHeaderActions(
        <InboxWorkspaceToolbar
          query={query}
          onQueryChange={setQuery}
          statusValue={statusValue}
          onStatusChange={handleStatusChange}
          escalationFilter={escalationFilter}
          onEscalationChange={handleEscalationFilterChange}
          attentionOnly={attentionOnly}
          onAttentionChange={setAttentionOnly}
          onNewRequest={openNewRequest}
        />,
      )
      return () => setHeaderActions(null)
    },
    [
      setHeaderActions,
      statusValue,
      query,
      escalationFilter,
      attentionOnly,
      handleStatusChange,
      handleEscalationFilterChange,
      openNewRequest,
    ],
  )

  function triggerRequest(requestId: string) {
    const startedAt = new Date().toISOString()
    patchRequestState(requestId, {
      phase: "queued",
      startedAt,
      lastCheckedAt: startedAt,
      finishedAt: undefined,
      error: undefined,
    })

    void runAction({
      label: `trigger:${requestId}`,
      request: () => chainIqApi.pipeline.process({ request_id: requestId }),
      successMessage: "Pipeline trigger started",
      successDescription: requestId,
    })
      .then(async () => {
        const phase = await startPolling(requestId, {
          initialPhase: "queued",
          intervalMs: 2000,
          timeoutMs: 45_000,
        })
        if (phase === "completed" || phase === "failed" || phase === "timed_out") {
          window.setTimeout(() => clearRequestState(requestId), 10_000)
        }
        router.refresh()
      })
      .catch(() => {
        patchRequestState(requestId, {
          phase: "failed",
          lastCheckedAt: new Date().toISOString(),
          finishedAt: new Date().toISOString(),
        })
        window.setTimeout(() => clearRequestState(requestId), 10_000)
      })
  }

  return (
    <div className="space-y-6">
      <Dialog open={newRequestOpen} onOpenChange={setNewRequestOpen}>
        <DialogContent className="w-[min(100vw-2rem,80rem)] max-w-none p-0" showCloseButton={false}>
          <DialogHeader className="border-b px-5 py-4">
            <DialogTitle>New Sourcing Case</DialogTitle>
            <DialogDescription>
              Provide messy input and progressively structure it before creation.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="max-h-[calc(100svh-9rem)] overflow-y-auto p-5">
            {newRequestOpen ? <CaseIntakeWizard embedded /> : null}
          </DialogBody>
        </DialogContent>
      </Dialog>

      {dataLoadError ? (
        <Card className="border-rose-200 bg-rose-50/70 text-rose-900">
          <CardContent className="py-3 text-sm">
            Backend data unavailable: {dataLoadError}. The inbox may be empty.
          </CardContent>
        </Card>
      ) : null}
      {Object.keys(requestLiveState).length > 0 ? (
        <Card className="border-blue-200 bg-blue-50/70 text-blue-900">
          <CardContent className="py-3 text-sm">
            {Object.keys(requestLiveState).length} request
            {Object.keys(requestLiveState).length > 1 ? "s are" : " is"} currently
            updating. Live row feedback is active.
          </CardContent>
        </Card>
      ) : null}

      <Card
        aria-busy={isFilterNavPending}
        className={cn(
          "animate-fade-in-up relative overflow-hidden transition-opacity duration-200",
          isFilterNavPending && "opacity-[0.98]",
        )}
        style={{ animationDelay: "80ms" }}
      >
        {isFilterNavPending ? (
          <div
            className="pointer-events-none absolute inset-x-0 top-0 z-10 h-0.5 bg-primary/75 motion-safe:animate-pulse"
            aria-hidden
          />
        ) : null}
        <CardContent className="p-0">
          <div
            className={cn(
              "overflow-x-auto transition-opacity duration-150",
              isSearchDeferring && "opacity-[0.9]",
            )}
          >
            <Table className="motion-safe:transition-[opacity] motion-safe:duration-150">
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[220px] px-4">
                    Project
                  </TableHead>
                  <TableHead className="min-w-[120px]">
                    Recommendation
                  </TableHead>
                  <TableHead className="min-w-[120px]">Category</TableHead>
                  <TableHead className="min-w-[100px]">Budget</TableHead>
                  <TableHead className="min-w-[80px]">Country</TableHead>
                  <TableHead className="min-w-[100px]">Status</TableHead>
                  <TableHead className="min-w-[120px]">Escalation</TableHead>
                  <TableHead className="min-w-[140px]">Scenario</TableHead>
                  <TableHead className="min-w-[100px]">Required By</TableHead>
                  <TableHead className="min-w-[150px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCases.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={10} className="py-8 text-center text-sm text-muted-foreground">
                      {cases.length === 0
                        ? "No cases for the current view."
                        : "No cases match your filters on this page."}
                    </TableCell>
                  </TableRow>
                ) : null}
                {filteredCases.map((entry) => {
                  const liveState = requestLiveState[entry.requestId]
                  const isLiveRunning =
                    liveState?.phase === "queued" || liveState?.phase === "running"
                  const recommendationTone =
                    entry.recommendationStatus === "not_evaluated"
                      ? "neutral"
                      : entry.recommendationStatus === "proceed"
                        ? "success"
                        : entry.recommendationStatus ===
                            "proceed_with_conditions"
                          ? "warning"
                          : "destructive"

                  return (
                    <TableRow
                      key={entry.requestId}
                      className={cn(
                        "group",
                        entry.needsAttention &&
                          "border-l-2 border-l-amber-400",
                        liveState?.phase === "completed" && "bg-emerald-50/40",
                        (liveState?.phase === "failed" ||
                          liveState?.phase === "timed_out") &&
                          "bg-rose-50/40",
                      )}
                    >
                      <TableCell className="px-4 py-3">
                        <Link
                          href={`/cases/${entry.requestId}`}
                          className="flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0">
                            <p className="font-medium">{entry.title}</p>
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                              {entry.businessUnit}
                            </p>
                          </div>
                          <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                        </Link>
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={displayRecommendationStatus(entry.recommendationStatus)}
                          tone={recommendationTone}
                        />
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.category || emptyCell()}
                      </TableCell>
                      <TableCell className="text-sm font-medium tabular-nums">
                        {formatCurrency(entry.budgetAmount, entry.currency)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.countryLabel
                          ? formatCountryDisplayName(entry.countryLabel)
                          : emptyCell()}
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={displayCaseStatus(entry.status)}
                          tone={entry.needsAttention ? "warning" : "neutral"}
                        />
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={displayEscalationStatus(entry.escalationStatus)}
                          tone={
                            entry.escalationStatus === "blocking"
                              ? "destructive"
                              : entry.escalationStatus === "advisory"
                                ? "warning"
                                : "neutral"
                          }
                        />
                      </TableCell>
                      <TableCell className="max-w-[180px] text-xs text-muted-foreground">
                        {entry.scenarioTags.length > 0
                          ? entry.scenarioTags.slice(0, 3).join(", ")
                          : emptyCell()}
                      </TableCell>
                      <TableCell
                        className="text-sm tabular-nums"
                        suppressHydrationWarning
                      >
                        {formatDate(entry.requiredByDate)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col items-start gap-2">
                          {entry.recommendationStatus === "not_evaluated" ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => triggerRequest(entry.requestId)}
                              disabled={
                                loadingAction === `trigger:${entry.requestId}` ||
                                isLiveRunning
                              }
                            >
                              {loadingAction === `trigger:${entry.requestId}` ||
                              isLiveRunning ? (
                                <>
                                  <Loader2 className="size-3.5 animate-spin" />
                                  Triggering...
                                </>
                              ) : (
                                <>
                                  <Play className="size-3.5" />
                                  Trigger now
                                </>
                              )}
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              Open case for actions
                            </span>
                          )}
                          {liveState ? (
                            <div className="space-y-1">
                              <StatusBadge
                                label={labelForLivePhase(liveState.phase)}
                                tone={toneForLivePhase(liveState.phase)}
                              />
                              {liveState.lastCheckedAt ? (
                                <p
                                  className="text-[11px] text-muted-foreground"
                                  suppressHydrationWarning
                                >
                                  Checked{" "}
                                  {formatDateTime(liveState.lastCheckedAt)}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between border-t px-4 py-3">
            <p className="text-sm text-muted-foreground">
              {total === 0
                ? "No results"
                : `Showing ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}
            </p>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1 || isFilterNavPending}
                onClick={() => handlePageChange(page - 1)}
              >
                <ChevronLeft className="size-4" />
                Previous
              </Button>
              <span className="px-2 text-sm tabular-nums text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= totalPages || isFilterNavPending}
                onClick={() => handlePageChange(page + 1)}
              >
                Next
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
