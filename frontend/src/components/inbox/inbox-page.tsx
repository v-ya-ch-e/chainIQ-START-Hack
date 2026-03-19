"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMemo, useState } from "react"
import { ArrowRight, Loader2, Play, Search, Sparkles } from "lucide-react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { CaseIntakeWizard } from "@/components/case-intake/case-intake-wizard"
import { JsonViewer } from "@/components/shared/json-viewer"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Textarea } from "@/components/ui/textarea"
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
import { formatCurrency, formatDate, formatDateTime } from "@/lib/data/formatters"
import { chainIqApi } from "@/lib/api/client"
import { usePipelineActionRunner } from "@/lib/pipeline/action-runner"
import {
  type PipelineLivePhase,
  useRequestStatusPoller,
} from "@/lib/pipeline/request-status-poller"
import type { CaseListItem } from "@/lib/types/case"
import { cn } from "@/lib/utils"

interface InboxPageProps {
  cases: CaseListItem[]
}

const statusOptions = [
  { value: "all", label: "All statuses" },
  { value: "pending_review", label: "Pending review" },
  { value: "recommended", label: "Recommended" },
  { value: "evaluated", label: "Evaluated" },
  { value: "escalated", label: "Escalated" },
]

const escalationOptions = [
  { value: "all", label: "All escalations" },
  { value: "none", label: "No escalation" },
  { value: "advisory", label: "Advisory" },
  { value: "blocking", label: "Blocking" },
]

function labelForLivePhase(phase: PipelineLivePhase) {
  switch (phase) {
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
    default:
      return "neutral" as const
  }
}

export function InboxPage({ cases }: InboxPageProps) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [escalationFilter, setEscalationFilter] = useState("all")
  const [newRequestOpen, setNewRequestOpen] = useState(false)
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [batchIds, setBatchIds] = useState("")
  const [concurrency, setConcurrency] = useState("5")
  const [batchResult, setBatchResult] = useState<unknown>(null)
  const {
    requestLiveState,
    startPolling,
    patchRequestState,
    clearRequestState,
  } = useRequestStatusPoller()
  const { loadingAction, error, fallback, message, runAction } =
    usePipelineActionRunner()

  const filteredCases = useMemo(() => {
    return cases.filter((entry) => {
      const normalizedQuery = query.trim().toLowerCase()
      const matchesQuery =
        !normalizedQuery ||
        entry.requestId.toLowerCase().includes(normalizedQuery) ||
        entry.title.toLowerCase().includes(normalizedQuery) ||
        entry.businessUnit.toLowerCase().includes(normalizedQuery) ||
        entry.countryLabel.toLowerCase().includes(normalizedQuery) ||
        entry.supplierLabel.toLowerCase().includes(normalizedQuery)

      const matchesStatus =
        statusFilter === "all" ? true : entry.status === statusFilter

      const matchesEscalation =
        escalationFilter === "all"
          ? true
          : entry.escalationStatus === escalationFilter

      const matchesAttention = attentionOnly ? entry.needsAttention : true

      return (
        matchesQuery && matchesStatus && matchesEscalation && matchesAttention
      )
    })
  }, [attentionOnly, cases, escalationFilter, query, statusFilter])
  const selectedStatusLabel =
    statusOptions.find((option) => option.value === statusFilter)?.label ??
    "All statuses"
  const selectedEscalationLabel =
    escalationOptions.find((option) => option.value === escalationFilter)?.label ??
    "All escalations"

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
      successMessage: `Pipeline trigger started for ${requestId}.`,
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

  function processBatch() {
    const requestIds = batchIds
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)
    if (requestIds.length === 0) return
    const startedAt = new Date().toISOString()
    for (const requestId of requestIds) {
      patchRequestState(requestId, {
        phase: "queued",
        startedAt,
        lastCheckedAt: startedAt,
        finishedAt: undefined,
        error: undefined,
      })
    }

    void runAction({
      label: "batch",
      request: () =>
        chainIqApi.pipeline.processBatch({
          request_ids: requestIds,
          concurrency: Number(concurrency) || 5,
        }),
      onSuccess: setBatchResult,
      successMessage: "Batch process submitted.",
    })
      .then(async () => {
        await Promise.allSettled(
          requestIds.map(async (requestId) => {
            const phase = await startPolling(requestId, {
              initialPhase: "queued",
              intervalMs: 2000,
              timeoutMs: 45_000,
            })
            if (
              phase === "completed" ||
              phase === "failed" ||
              phase === "timed_out"
            ) {
              window.setTimeout(() => clearRequestState(requestId), 10_000)
            }
          }),
        )
        router.refresh()
      })
      .catch(() => {
        const failedAt = new Date().toISOString()
        for (const requestId of requestIds) {
          patchRequestState(requestId, {
            phase: "failed",
            lastCheckedAt: failedAt,
            finishedAt: failedAt,
          })
          window.setTimeout(() => clearRequestState(requestId), 10_000)
        }
      })
  }

  return (
    <div className="space-y-6">
      <div className="animate-fade-in-up flex items-start justify-between">
        <SectionHeading
          eyebrow="Inbox"
          title="Case triage queue"
          description="Search, filter, and drill into individual sourcing cases."
        />
        <Button onClick={() => setNewRequestOpen(true)}>
          <Sparkles className="mr-2 size-4" />
          New Request
        </Button>
      </div>

      <Dialog open={newRequestOpen} onOpenChange={setNewRequestOpen}>
        <DialogContent className="w-[min(100vw-2rem,80rem)] max-w-none p-0" showCloseButton={false}>
          <DialogHeader className="border-b px-5 py-4">
            <DialogTitle>New Sourcing Case</DialogTitle>
            <DialogDescription>
              Provide messy input and progressively structure it before creation.
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="max-h-[calc(100svh-9rem)] overflow-y-auto p-5">
            <CaseIntakeWizard embedded />
          </DialogBody>
        </DialogContent>
      </Dialog>

      {message ? (
        <Card className="border-emerald-200 bg-emerald-50/70 text-emerald-900">
          <CardContent className="py-3 text-sm">{message}</CardContent>
        </Card>
      ) : null}
      {error ? (
        <Card className="border-rose-200 bg-rose-50/70 text-rose-900">
          <CardContent className="py-3 text-sm">{error}</CardContent>
        </Card>
      ) : null}
      {fallback ? (
        <Card className="border-amber-200 bg-amber-50/70 text-amber-900">
          <CardContent className="py-3 text-sm">
            Runs endpoint degraded. Other trigger actions remain usable. {fallback}
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

      <Card className="animate-fade-in-up" style={{ animationDelay: "80ms" }}>
        <CardHeader className="border-b pb-4">
          <CardTitle className="sr-only">Filters</CardTitle>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search request ID, title, supplier, business unit, country..."
                className="h-9 pl-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Select
                value={statusFilter}
                onValueChange={(v) => setStatusFilter(v ?? "all")}
              >
                <SelectTrigger className="w-[160px]">
                  <span className="truncate">{selectedStatusLabel}</span>
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
                onValueChange={(value) => setEscalationFilter(value ?? "all")}
              >
                <SelectTrigger className="w-[160px]">
                  <span className="truncate">{selectedEscalationLabel}</span>
                </SelectTrigger>
                <SelectContent>
                  {escalationOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={attentionOnly}
                  onCheckedChange={(checked) =>
                    setAttentionOnly(checked === true)
                  }
                />
                Needs attention only
              </label>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[200px] px-4">
                    Request
                  </TableHead>
                  <TableHead className="min-w-[120px]">Category</TableHead>
                  <TableHead className="min-w-[120px]">Business Unit</TableHead>
                  <TableHead className="min-w-[80px]">Country</TableHead>
                  <TableHead className="min-w-[100px]">Budget</TableHead>
                  <TableHead className="min-w-[100px]">Required By</TableHead>
                  <TableHead className="min-w-[120px]">Last Updated</TableHead>
                  <TableHead className="min-w-[100px]">Status</TableHead>
                  <TableHead className="min-w-[120px]">Escalation</TableHead>
                  <TableHead className="min-w-[160px]">Scenario</TableHead>
                  <TableHead className="min-w-[120px]">
                    Recommendation
                  </TableHead>
                  <TableHead className="min-w-[150px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCases.map((entry) => {
                  const liveState = requestLiveState[entry.requestId]
                  const isLiveRunning =
                    liveState?.phase === "queued" || liveState?.phase === "running"
                  const recommendationTone =
                    entry.recommendationStatus === "proceed"
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
                            <p className="font-medium">{entry.requestId}</p>
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                              {entry.title}
                            </p>
                          </div>
                          <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                        </Link>
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.category}
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.businessUnit}
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.countryLabel}
                      </TableCell>
                      <TableCell className="text-sm font-medium tabular-nums">
                        {formatCurrency(entry.budgetAmount, entry.currency)}
                      </TableCell>
                      <TableCell className="text-sm tabular-nums">
                        {formatDate(entry.requiredByDate)}
                      </TableCell>
                      <TableCell className="text-sm tabular-nums">
                        {formatDate(entry.lastUpdated)}
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={entry.status.replaceAll("_", " ")}
                          tone={entry.needsAttention ? "warning" : "neutral"}
                        />
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={entry.escalationStatus}
                          tone={
                            entry.escalationStatus === "blocking"
                              ? "destructive"
                              : entry.escalationStatus === "advisory"
                                ? "warning"
                                : "neutral"
                          }
                        />
                      </TableCell>
                      <TableCell className="max-w-[200px] text-xs text-muted-foreground">
                        {entry.scenarioTags.slice(0, 3).join(", ") || "standard"}
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={entry.recommendationStatus.replaceAll(
                            "_",
                            " ",
                          )}
                          tone={recommendationTone}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col items-start gap-2">
                          {entry.status === "received" ? (
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
                                <p className="text-[11px] text-muted-foreground">
                                  Checked {formatDateTime(liveState.lastCheckedAt)}
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Advanced actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Bulk trigger requests from Inbox (moved from Pipeline Ops).
          </p>
          <Textarea
            value={batchIds}
            onChange={(event) => setBatchIds(event.target.value)}
            placeholder="REQ-000001,REQ-000004"
            className="min-h-20"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={concurrency}
              onChange={(event) => setConcurrency(event.target.value)}
              placeholder="Concurrency (1-20)"
              type="number"
              className="w-[220px]"
            />
            <Button
              onClick={processBatch}
              disabled={loadingAction === "batch" || batchIds.trim().length === 0}
            >
              {loadingAction === "batch" ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Play className="size-3.5" />
                  Process batch
                </>
              )}
            </Button>
            <Link
              href="/audit"
              className={buttonVariants({ variant: "outline" })}
            >
              View audit diagnostics
            </Link>
          </div>
        </CardContent>
      </Card>

      {batchResult ? <JsonViewer title="Batch Result" value={batchResult} /> : null}
    </div>
  )
}
