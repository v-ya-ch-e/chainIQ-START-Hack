"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMemo, useState } from "react"
import { ArrowRight, Loader2, Play, Search, Sparkles } from "lucide-react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { JsonViewer } from "@/components/shared/json-viewer"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatCurrency, formatDate } from "@/lib/data/formatters"
import { chainIqApi } from "@/lib/api/client"
import { usePipelineActionRunner } from "@/lib/pipeline/action-runner"
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

export function InboxPage({ cases }: InboxPageProps) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [escalationFilter, setEscalationFilter] = useState("all")
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [batchIds, setBatchIds] = useState("")
  const [concurrency, setConcurrency] = useState("5")
  const [batchResult, setBatchResult] = useState<unknown>(null)
  const { loadingAction, error, fallback, message, runAction } =
    usePipelineActionRunner()

  const isAnyActionRunning = loadingAction !== null

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

  function triggerRequest(requestId: string) {
    void runAction({
      label: `trigger:${requestId}`,
      request: () => chainIqApi.pipeline.process({ request_id: requestId }),
      successMessage: `Pipeline trigger started for ${requestId}.`,
    })
      .then(() => router.refresh())
      .catch(() => {
        // Error state is handled by shared action runner.
      })
  }

  function processBatch() {
    const requestIds = batchIds
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)
    if (requestIds.length === 0) return

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
      .then(() => router.refresh())
      .catch(() => {
        // Error state is handled by shared action runner.
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
        <Button render={<Link href="/cases/new" />}>
          <Sparkles className="mr-2 size-4" />
          New Request
        </Button>
      </div>

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
                  <SelectValue />
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
                  <SelectValue />
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
                        {entry.status === "received" ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => triggerRequest(entry.requestId)}
                            disabled={isAnyActionRunning}
                          >
                            {loadingAction === `trigger:${entry.requestId}` ? (
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
              disabled={isAnyActionRunning || batchIds.trim().length === 0}
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
            <Button variant="outline" render={<Link href="/audit" />}>
              View audit diagnostics
            </Button>
          </div>
        </CardContent>
      </Card>

      {batchResult ? <JsonViewer title="Batch Result" value={batchResult} /> : null}
    </div>
  )
}
