"use client"

import { Activity, Download, Loader2, Play, RefreshCw, ShieldCheck, TimerReset } from "lucide-react"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"

import { SectionHeading } from "@/components/shared/section-heading"
import { JsonViewer } from "@/components/shared/json-viewer"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  scoreTone,
  severityTone,
} from "@/lib/data/formatters"
import type { CaseDetail } from "@/lib/types/case"
import { cn } from "@/lib/utils"
import { chainIqApi } from "@/lib/api/client"
import { usePipelineActionRunner } from "@/lib/pipeline/action-runner"
import {
  classifyPipelineStatus,
  useRequestStatusPoller,
} from "@/lib/pipeline/request-status-poller"

interface CaseWorkspaceProps {
  data: CaseDetail
  initialTab?: CaseTab
  createdFromIntake?: boolean
}

type CaseTab = "overview" | "suppliers" | "escalations" | "audit"

function livePhaseLabel(phase: "queued" | "running" | "completed" | "failed" | "unknown" | "timed_out") {
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

function livePhaseTone(phase: "queued" | "running" | "completed" | "failed" | "unknown" | "timed_out") {
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

export function CaseWorkspace({
  data,
  initialTab = "overview",
  createdFromIntake = false,
}: CaseWorkspaceProps) {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<CaseTab>(initialTab)
  const [contentMinHeight, setContentMinHeight] = useState<number | null>(null)
  const [runId, setRunId] = useState("")
  const [statusResult, setStatusResult] = useState<unknown>(null)
  const [pipelineResult, setPipelineResult] = useState<unknown>(null)
  const [runsResult, setRunsResult] = useState<unknown>(null)
  const [runDetailResult, setRunDetailResult] = useState<unknown>(null)
  const [auditResult, setAuditResult] = useState<unknown>(null)
  const [summaryResult, setSummaryResult] = useState<unknown>(null)
  const [stepResult, setStepResult] = useState<unknown>(null)
  const {
    loadingAction,
    error,
    fallback,
    message,
    setMessage,
    runAction,
    actionLifecycleByLabel,
    lastActionLifecycle,
  } = usePipelineActionRunner()
  const { requestLiveState, startPolling, patchRequestState } =
    useRequestStatusPoller()
  const blockingIssues = data.validationIssues.filter((issue) => issue.blocking)
  const recommendedSupplier = data.recommendation.recommendedSupplier
  const evaluatedSuppliers =
    data.supplierShortlist.length + data.excludedSuppliers.length
  const hasShortlist = data.supplierShortlist.length > 0
  const lowestPrice = hasShortlist
    ? Math.min(...data.supplierShortlist.map((entry) => entry.totalPrice))
    : null
  const fastestExpeditedLeadTime = hasShortlist
    ? Math.min(...data.supplierShortlist.map((entry) => entry.expeditedLeadTimeDays))
    : null
  const activeEscalation =
    data.escalations.find((entry) => entry.status !== "resolved") ??
    data.escalations[0] ??
    null
  const overviewRef = useRef<HTMLDivElement>(null)
  const suppliersRef = useRef<HTMLDivElement>(null)
  const escalationsRef = useRef<HTMLDivElement>(null)
  const auditRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const tabPanelMap: Record<CaseTab, HTMLDivElement | null> = {
      overview: overviewRef.current,
      suppliers: suppliersRef.current,
      escalations: escalationsRef.current,
      audit: auditRef.current,
    }

    const updateHeight = () => {
      const activePanel = tabPanelMap[activeTab]
      if (!activePanel) return
      setContentMinHeight(activePanel.offsetHeight)
    }

    const frame = window.requestAnimationFrame(updateHeight)
    window.addEventListener("resize", updateHeight)

    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener("resize", updateHeight)
    }
  }, [activeTab, data.id])

  useEffect(() => {
    if (createdFromIntake) {
      setMessage(`Case ${data.id} created successfully.`)
    }
  }, [createdFromIntake, data.id, setMessage])

  function handleRerun() {
    const startedAt = new Date().toISOString()
    patchRequestState(data.id, {
      phase: "queued",
      startedAt,
      lastCheckedAt: startedAt,
      finishedAt: undefined,
      error: undefined,
    })
    void runAction({
      label: "rerun",
      request: () =>
        chainIqApi.pipeline.process({
          request_id: data.id,
        }),
      successMessage: `Pipeline re-run started for ${data.id}.`,
    })
      .then(async () => {
        await startPolling(data.id, {
          initialPhase: "queued",
          intervalMs: 2000,
          timeoutMs: 45_000,
        })
        router.refresh()
      })
      .catch(() => {
        patchRequestState(data.id, {
          phase: "failed",
          lastCheckedAt: new Date().toISOString(),
          finishedAt: new Date().toISOString(),
        })
      })
  }

  function handleStatus() {
    void runAction({
      label: "status",
      request: () => chainIqApi.pipeline.status(data.id),
      onSuccess: (result) => {
        setStatusResult(result)
        const phase = classifyPipelineStatus(result)
        patchRequestState(data.id, {
          phase,
          startedAt:
            requestLiveState[data.id]?.startedAt ?? new Date().toISOString(),
          lastCheckedAt: new Date().toISOString(),
          ...(phase === "completed" || phase === "failed"
            ? { finishedAt: new Date().toISOString() }
            : {}),
          statusPayload: result,
        })
      },
      successMessage: `Fetched latest pipeline status for ${data.id}.`,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleResult() {
    void runAction({
      label: "result",
      request: () => chainIqApi.pipeline.result(data.id),
      onSuccess: setPipelineResult,
      successMessage: `Fetched latest pipeline result for ${data.id}.`,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleRunDiagnostics() {
    void runAction({
      label: "runs",
      request: () => chainIqApi.pipeline.runs({ limit: 25, skip: 0 }),
      onSuccess: setRunsResult,
      successMessage: "Fetched recent pipeline runs.",
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleRunDetail() {
    if (!runId.trim()) return
    void runAction({
      label: "run",
      request: () => chainIqApi.pipeline.run(runId.trim()),
      onSuccess: setRunDetailResult,
      successMessage: `Fetched run details for ${runId.trim()}.`,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleAuditTrail() {
    void runAction({
      label: "audit",
      request: () => chainIqApi.pipeline.audit(data.id, { limit: 100, skip: 0 }),
      onSuccess: setAuditResult,
      successMessage: `Fetched audit trail for ${data.id}.`,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleAuditSummary() {
    void runAction({
      label: "summary",
      request: () => chainIqApi.pipeline.auditSummary(data.id),
      onSuccess: setSummaryResult,
      successMessage: `Fetched audit summary for ${data.id}.`,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleStep(step: "fetch" | "validate" | "filter" | "comply" | "rank" | "escalate") {
    const startedAt = new Date().toISOString()
    patchRequestState(data.id, {
      phase: "running",
      startedAt,
      lastCheckedAt: startedAt,
      finishedAt: undefined,
      error: undefined,
    })
    void runAction({
      label: `step:${step}`,
      request: () => chainIqApi.pipeline.steps[step]({ request_id: data.id }),
      onSuccess: setStepResult,
      successMessage: `Executed ${step} step for ${data.id}.`,
    })
      .then(async () => {
        await startPolling(data.id, {
          initialPhase: "running",
          intervalMs: 2000,
          timeoutMs: 30_000,
        })
        router.refresh()
      })
      .catch(() => {
        patchRequestState(data.id, {
          phase: "failed",
          lastCheckedAt: new Date().toISOString(),
          finishedAt: new Date().toISOString(),
        })
      })
  }

  function handleExport() {
    const payload = JSON.stringify(data, null, 2)
    const blob = new Blob([payload], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `${data.id}-audit-export.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    setMessage(`Exported ${data.id} payload as JSON.`)
  }

  function handleEscalate() {
    router.push(`/escalations?caseId=${data.id}`)
  }

  const requestLive = requestLiveState[data.id]
  const activeActionLifecycle = loadingAction
    ? actionLifecycleByLabel[loadingAction] ?? null
    : null

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="animate-fade-in-up flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <StatusBadge
              label={data.rawRequest.status.replaceAll("_", " ")}
              tone="neutral"
            />
            <StatusBadge
              label={data.recommendation.status.replaceAll("_", " ")}
              tone={
                data.recommendation.status === "proceed"
                  ? "success"
                  : data.recommendation.status === "proceed_with_conditions"
                    ? "warning"
                    : "destructive"
              }
            />
            <StatusBadge
              label={`${data.rawRequest.categoryL1} / ${data.rawRequest.categoryL2}`}
              tone="info"
            />
          </div>
          <SectionHeading
            eyebrow={data.id}
            title={data.title}
            description={`${data.rawRequest.country} · ${data.rawRequest.businessUnit} · created ${formatDateTime(data.rawRequest.createdAt)} · required by ${formatDate(data.rawRequest.requiredByDate)}`}
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRerun}
            disabled={loadingAction !== null}
          >
            {loadingAction === "rerun" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Play className="size-3.5" />
            )}
            {loadingAction === "rerun" ? "Re-running..." : "Re-run"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleStatus}
            disabled={loadingAction !== null}
          >
            {loadingAction === "status" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Activity className="size-3.5" />
            )}
            Status
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleResult}
            disabled={loadingAction !== null}
          >
            {loadingAction === "result" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <ShieldCheck className="size-3.5" />
            )}
            Result
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="size-3.5" />
            Export
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setActiveTab("audit")}
          >
            <ShieldCheck className="size-3.5" />
            Audit
          </Button>
          <Button size="sm" onClick={handleEscalate}>
            <TimerReset className="size-3.5" />
            Escalate
          </Button>
        </div>
      </div>

      {error ? (
        <Card className="border-rose-200 bg-rose-50/70 text-rose-900">
          <CardContent className="py-3 text-sm">{error}</CardContent>
        </Card>
      ) : null}

      {message ? (
        <Card className="border-emerald-200 bg-emerald-50/70 text-emerald-900">
          <CardContent className="py-3 text-sm">{message}</CardContent>
        </Card>
      ) : null}
      {fallback ? (
        <Card className="border-amber-200 bg-amber-50/70 text-amber-900">
          <CardContent className="py-3 text-sm">
            Runs endpoint degraded. Other pipeline actions remain usable. {fallback}
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-blue-200 bg-blue-50/60">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-blue-800">
              Live run state
            </p>
            <div className="flex flex-wrap items-center gap-1.5">
              <StatusBadge
                label={
                  requestLive ? livePhaseLabel(requestLive.phase) : "No live run"
                }
                tone={requestLive ? livePhaseTone(requestLive.phase) : "neutral"}
              />
              {activeActionLifecycle ? (
                <StatusBadge
                  label={`Action: ${activeActionLifecycle.label}`}
                  tone={activeActionLifecycle.phase === "error" ? "destructive" : "info"}
                />
              ) : null}
              {lastActionLifecycle ? (
                <StatusBadge
                  label={`Last: ${lastActionLifecycle.phase}`}
                  tone={
                    lastActionLifecycle.phase === "success"
                      ? "success"
                      : lastActionLifecycle.phase === "error"
                        ? "destructive"
                        : "neutral"
                  }
                />
              ) : null}
            </div>
          </div>
          <div className="text-right text-xs text-blue-900/70">
            <p>
              Last checked:{" "}
              {requestLive?.lastCheckedAt
                ? formatDateTime(requestLive.lastCheckedAt)
                : "Not yet"}
            </p>
            <p>
              Last transition:{" "}
              {lastActionLifecycle?.finishedAt
                ? formatDateTime(lastActionLifecycle.finishedAt)
                : "No completed action"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Primary summary strip */}
      <section className="animate-fade-in-up grid gap-4 xl:grid-cols-[1.2fr_0.8fr]" style={{ animationDelay: "80ms" }}>
        <Card className="border-primary/20 bg-primary/[0.03]">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <StatusBadge
                label={data.outcomeLabel}
                tone={
                  data.recommendation.status === "proceed"
                    ? "success"
                    : "destructive"
                }
              />
              <StatusBadge
                label={data.recommendation.approvalTier}
                tone="info"
              />
              <StatusBadge
                label={`${data.recommendation.quotesRequired} quotes`}
                tone="neutral"
              />
            </div>
            <CardTitle className="mt-2 text-lg font-semibold tracking-tight">
              {recommendedSupplier ?? "Human review required before award"}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <p className="text-sm leading-relaxed text-muted-foreground">
                {data.recommendation.reason}
              </p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {data.recommendation.rationale}
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <KpiCell
                label="Total Price"
                value={
                  data.recommendation.totalPrice
                    ? formatCurrency(
                        data.recommendation.totalPrice,
                        data.recommendation.currency,
                      )
                    : formatCurrency(
                        data.recommendation.minimumBudgetRequired,
                        data.recommendation.currency,
                      )
                }
                helper={
                  data.recommendation.totalPrice
                    ? "Recommended commercial value"
                    : "Minimum viable budget"
                }
              />
              <KpiCell
                label="Compliance"
                value={data.recommendation.complianceStatus}
                helper="Policy posture"
              />
              <KpiCell
                label="Blocking Issues"
                value={blockingIssues.length}
                helper="Validation or policy blockers"
              />
              <KpiCell
                label="Escalations"
                value={data.escalations.length}
                helper="Workflow actions opened"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Outcome summary</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <FieldCell
              label="Recommended Supplier"
              value={
                recommendedSupplier ??
                data.recommendation.preferredSupplierIfResolved ??
                "Pending human resolution"
              }
              variant="emphasis"
            />
            <FieldCell
              label="Approval Tier"
              value={data.recommendation.approvalTier}
            />
            <FieldCell
              label="Quotes Required"
              value={`${data.recommendation.quotesRequired}`}
            />
            <FieldCell
              label="Managers"
              value={
                data.recommendation.managers?.length
                  ? data.recommendation.managers.join(", ")
                  : "Not specified"
              }
            />
            <FieldCell
              label="Deviation Approvers"
              value={
                data.recommendation.deviationApprovers?.length
                  ? data.recommendation.deviationApprovers.join(", ")
                  : "Not specified"
              }
            />
            <FieldCell
              label="Country Scope"
              value={data.rawRequest.deliveryCountries.join(", ")}
            />
            <FieldCell
              label="Scenario Tags"
              value={data.rawRequest.scenarioTags.join(", ") || "standard"}
            />
            <FieldCell
              label="Budget"
              value={formatCurrency(
                data.rawRequest.budgetAmount,
                data.rawRequest.currency,
              )}
              variant="default"
            />
            <FieldCell
              label="Tier Range"
              value={`${formatCurrency(data.recommendation.minAmount ?? null, data.recommendation.currency)} - ${formatCurrency(data.recommendation.maxAmount ?? null, data.recommendation.currency)}`}
              variant="default"
            />
            <FieldCell
              label="Last Updated"
              value={formatDateTime(data.lastUpdated)}
            />
          </CardContent>
        </Card>
      </section>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as CaseTab)}
        className="animate-fade-in-up space-y-6"
        style={{ animationDelay: "160ms" }}
      >
        <TabsList
          variant="line"
          className="w-full justify-start rounded-none border-b border-border/70 p-0"
        >
          <TabsTrigger value="overview" className="px-5 py-3">
            Overview
          </TabsTrigger>
          <TabsTrigger value="suppliers" className="px-5 py-3">
            Suppliers
          </TabsTrigger>
          <TabsTrigger value="escalations" className="px-5 py-3">
            Escalations
          </TabsTrigger>
          <TabsTrigger value="audit" className="px-5 py-3">
            Audit Trace
          </TabsTrigger>
        </TabsList>

        <div
          className="transition-[min-height] duration-300 ease-out"
          style={contentMinHeight ? { minHeight: `${contentMinHeight}px` } : undefined}
        >
          {/* Overview tab */}
          <TabsContent
            ref={overviewRef}
            value="overview"
            className="space-y-6 transition-all duration-200 ease-out"
          >
          <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
            <Card>
              <CardHeader>
                <CardTitle>Original request</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="rounded-lg border bg-muted/30 p-4">
                  <p className="text-sm leading-relaxed">
                    {data.rawRequest.requestText}
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <FieldCell
                    label="Request channel"
                    value={data.rawRequest.requestChannel}
                  />
                  <FieldCell
                    label="Request ID"
                    value={data.rawRequest.requestId}
                  />
                  <FieldCell
                    label="Request language"
                    value={data.rawRequest.requestLanguage}
                  />
                  <FieldCell
                    label="Business unit"
                    value={data.rawRequest.businessUnit}
                  />
                  <FieldCell
                    label="Requester ID"
                    value={data.rawRequest.requesterId ?? "Not specified"}
                  />
                  <FieldCell label="Site" value={data.rawRequest.site} />
                  <FieldCell
                    label="Requester role"
                    value={data.rawRequest.requesterRole}
                  />
                  <FieldCell
                    label="Submitted for"
                    value={data.rawRequest.submittedForId}
                  />
                  <FieldCell
                    label="Preferred supplier"
                    value={
                      data.rawRequest.preferredSupplierMentioned ?? "Not stated"
                    }
                  />
                  <FieldCell
                    label="Incumbent supplier"
                    value={data.rawRequest.incumbentSupplier ?? "Not stated"}
                  />
                  <FieldCell
                    label="Contract type"
                    value={data.rawRequest.contractTypeRequested}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Interpreted requirements</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                {data.interpretedRequirements.map((item) => (
                  <div
                    key={item.label}
                    className={cn(
                      "rounded-lg border p-3.5",
                      item.emphasis
                        ? "border-primary/30 bg-primary/[0.05]"
                        : "bg-muted/20",
                    )}
                  >
                    <div className="flex items-center gap-1.5">
                      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        {item.label}
                      </p>
                      {item.inferred ? (
                        <StatusBadge label="Inferred" tone="info" />
                      ) : null}
                    </div>
                    <p
                      className={cn(
                        "mt-1 text-sm leading-relaxed",
                        item.emphasis ? "font-medium" : "text-muted-foreground",
                      )}
                    >
                      {item.value}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <Card className="bg-card/70">
              <CardHeader>
                <CardTitle>Validation & issues</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.validationIssues.map((issue) => (
                  <div
                    key={issue.issueId}
                    className="rounded-lg border bg-background/80 p-3.5"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <StatusBadge label={issue.issueId} tone="neutral" />
                      <StatusBadge
                        label={issue.severity}
                        tone={severityTone(issue.severity)}
                      />
                      <StatusBadge
                        label={issue.type.replaceAll("_", " ")}
                        tone="info"
                      />
                      {issue.blocking ? (
                        <StatusBadge label="blocking" tone="destructive" />
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm leading-relaxed">
                      {issue.description}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      {issue.actionRequired}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="bg-card/70">
              <CardHeader>
                <CardTitle>Policy evaluation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.policyCards.map((policy) => (
                  <div
                    key={policy.ruleId}
                    className="rounded-lg border bg-background/80 p-3.5"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <StatusBadge label={policy.ruleId} tone="info" />
                      <StatusBadge
                        label={policy.status}
                        tone={
                          policy.status === "satisfied"
                            ? "success"
                            : policy.status === "conflict"
                              ? "destructive"
                              : "neutral"
                        }
                      />
                    </div>
                    <h3 className="mt-2 text-sm font-semibold">
                      {policy.title}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      {policy.summary}
                    </p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      {policy.detail.map((detail) => (
                        <FieldCell
                          key={detail.label}
                          label={detail.label}
                          value={detail.value}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
          </TabsContent>

          {/* Suppliers tab */}
          <TabsContent
            ref={suppliersRef}
            value="suppliers"
            className="space-y-5 transition-all duration-200 ease-out"
          >
          <div className="space-y-5">
            <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <MiniMetric
                label="Suppliers evaluated"
                value={evaluatedSuppliers}
                helper="Shortlist plus excluded rows"
              />
              <MiniMetric
                label="Compliant suppliers"
                value={data.supplierShortlist.length}
                helper="Suppliers still eligible after policy filters"
              />
              <MiniMetric
                label="Lowest compliant price"
                value={formatCurrency(lowestPrice, data.recommendation.currency)}
                helper="Best commercial baseline"
              />
              <MiniMetric
                label="Fastest expedited lead time"
                value={
                  fastestExpeditedLeadTime === null
                    ? "Not available"
                    : `${fastestExpeditedLeadTime} days`
                }
                helper="Closest feasible delivery option"
              />
            </section>

            <section className="space-y-4">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Supplier comparison</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="overflow-x-auto rounded-lg border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="px-3">Rank</TableHead>
                          <TableHead>Supplier</TableHead>
                          <TableHead>Pricing Tier</TableHead>
                          <TableHead>Total</TableHead>
                          <TableHead>Lead Time</TableHead>
                          <TableHead>Quality</TableHead>
                          <TableHead>Risk</TableHead>
                          <TableHead>ESG</TableHead>
                          <TableHead>Flags</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.supplierShortlist.map((supplier) => (
                          <TableRow
                            key={supplier.supplierId}
                            className={
                              supplier.rank === 1 ? "bg-emerald-50/40" : ""
                            }
                          >
                            <TableCell className="px-3">
                              <div className="space-y-1">
                                <p className="text-base font-semibold tabular-nums">
                                  #{supplier.rank}
                                </p>
                                {supplier.rank === 1 ? (
                                  <StatusBadge label="Top option" tone="success" />
                                ) : null}
                              </div>
                            </TableCell>
                            <TableCell className="align-top">
                              <div className="space-y-1">
                                <p className="font-medium">
                                  {supplier.supplierName}
                                </p>
                                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                                  {supplier.supplierId}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {supplier.countryHq ?? "N/A"} ·{" "}
                                  {supplier.currency ?? data.recommendation.currency}
                                </p>
                                <p className="max-w-[260px] text-xs leading-relaxed text-muted-foreground">
                                  {supplier.recommendationNote}
                                </p>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm">
                              <p>{supplier.pricingTierApplied}</p>
                              <p className="text-xs text-muted-foreground">
                                {supplier.region ?? "N/A"} · qty{" "}
                                {supplier.minQuantity ?? "?"}-{supplier.maxQuantity ?? "?"}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                MOQ {supplier.moq ?? "N/A"}
                              </p>
                            </TableCell>
                            <TableCell className="font-medium tabular-nums">
                              <div>
                                {formatCurrency(
                                  supplier.totalPrice,
                                  data.recommendation.currency,
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Unit{" "}
                                {formatCurrency(
                                  supplier.unitPrice,
                                  data.recommendation.currency,
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Exp.{" "}
                                {formatCurrency(
                                  supplier.expeditedTotal,
                                  data.recommendation.currency,
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Exp unit{" "}
                                {formatCurrency(
                                  supplier.expeditedUnitPrice,
                                  data.recommendation.currency,
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="tabular-nums">
                              <div>{supplier.standardLeadTimeDays}d std</div>
                              <div className="text-xs text-muted-foreground">
                                {supplier.expeditedLeadTimeDays}d exp
                              </div>
                            </TableCell>
                            <TableCell
                              className={scoreTone(supplier.qualityScore)}
                            >
                              {supplier.qualityScore}
                            </TableCell>
                            <TableCell
                              className={scoreTone(supplier.riskScore, true)}
                            >
                              {supplier.riskScore}
                            </TableCell>
                            <TableCell className={scoreTone(supplier.esgScore)}>
                              {supplier.esgScore}
                            </TableCell>
                            <TableCell>
                              <div className="flex max-w-[180px] flex-wrap gap-1">
                                {supplier.preferred ? (
                                  <StatusBadge label="Preferred" tone="info" />
                                ) : null}
                                {supplier.incumbent ? (
                                  <StatusBadge label="Incumbent" tone="neutral" />
                                ) : null}
                                {supplier.policyCompliant ? (
                                  <StatusBadge label="Compliant" tone="success" />
                                ) : (
                                  <StatusBadge label="Conflict" tone="destructive" />
                                )}
                                {supplier.dataResidencySupported ? (
                                  <StatusBadge label="Data residency" tone="info" />
                                ) : null}
                                {supplier.coversDeliveryCountry ? (
                                  <StatusBadge label="Covers country" tone="neutral" />
                                ) : null}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>

              <div
                className={cn(
                  "grid gap-4",
                  data.historicalPrecedent ? "xl:grid-cols-2" : "xl:grid-cols-1",
                )}
              >
                <Card className="bg-card/70">
                  <CardHeader>
                    <CardTitle>Excluded suppliers</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {data.excludedSuppliers.map((supplier) => (
                      <div
                        key={supplier.supplierId}
                        className="rounded-lg border bg-background/80 p-3.5"
                      >
                        <div className="flex flex-wrap items-center gap-1.5">
                          <StatusBadge
                            label={supplier.supplierId}
                            tone="neutral"
                          />
                          <StatusBadge
                            label={
                              supplier.hardExclusion
                                ? "hard exclusion"
                                : "not shortlisted"
                            }
                            tone={
                              supplier.hardExclusion ? "destructive" : "warning"
                            }
                          />
                        </div>
                        <p className="mt-2 text-sm font-medium">
                          {supplier.supplierName}
                        </p>
                        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                          {supplier.reason}
                        </p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {data.historicalPrecedent ? (
                  <Card className="border-blue-200 bg-blue-50/50">
                    <CardHeader>
                      <CardTitle>{data.historicalPrecedent.title}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm leading-relaxed text-muted-foreground">
                        {data.historicalPrecedent.description}
                      </p>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        {data.historicalPrecedent.metrics.map((metric) => (
                          <FieldCell
                            key={metric.label}
                            label={metric.label}
                            value={metric.value}
                            variant="default"
                          />
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            </section>
          </div>
          </TabsContent>

          {/* Escalations tab */}
          <TabsContent
            ref={escalationsRef}
            value="escalations"
            className="space-y-5 transition-all duration-200 ease-out"
          >
            <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <MiniMetric
                label="Escalations total"
                value={data.escalations.length}
                helper="All escalation objects on this case"
              />
              <MiniMetric
                label="Open escalations"
                value={data.escalations.filter((entry) => entry.status === "open").length}
                helper="Awaiting first human action"
              />
              <MiniMetric
                label="Blocking escalations"
                value={data.escalations.filter((entry) => entry.blocking).length}
                helper="Prevent autonomous progression"
              />
              <MiniMetric
                label="Resolved escalations"
                value={data.escalations.filter((entry) => entry.status === "resolved").length}
                helper="Closed and no longer actionable"
              />
            </section>

            {data.escalations.some((entry) => entry.blocking) ? (
              <Card className="border-rose-200 bg-rose-50/60">
                <CardContent className="px-5 py-4">
                  <p className="text-xs font-medium uppercase tracking-wider text-rose-700">
                    Blocking escalation state
                  </p>
                  <h3 className="mt-1 text-base font-semibold text-rose-900">
                    Autonomous progression is paused
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-rose-800/70">
                    One or more escalation objects require human review before the
                    sourcing case can proceed to award.
                  </p>
                </CardContent>
              </Card>
            ) : null}

            {activeEscalation ? (
              <Card className="border-primary/20 bg-primary/[0.04]">
                <CardHeader>
                  <CardTitle>Current escalation focus</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <StatusBadge label={activeEscalation.escalationId} tone="neutral" />
                      <StatusBadge label={activeEscalation.rule} tone="info" />
                      <StatusBadge
                        label={activeEscalation.status}
                        tone={
                          activeEscalation.status === "resolved"
                            ? "success"
                            : "destructive"
                        }
                      />
                      <StatusBadge
                        label={activeEscalation.blocking ? "blocking" : "advisory"}
                        tone={activeEscalation.blocking ? "destructive" : "warning"}
                      />
                    </div>
                    <h3 className="text-base font-semibold">
                      Escalate to {activeEscalation.escalateTo}
                    </h3>
                    {activeEscalation.ruleLabel ? (
                      <p className="text-sm leading-relaxed text-muted-foreground">
                        {activeEscalation.ruleLabel}
                      </p>
                    ) : null}
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {activeEscalation.trigger}
                    </p>
                  </div>
                  <FieldCell
                    label="Next action"
                    value={activeEscalation.nextAction}
                    variant="default"
                  />
                </CardContent>
              </Card>
            ) : null}

            <Card className="bg-muted/15">
              <CardHeader>
                <CardTitle>Escalation queue</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="overflow-x-auto rounded-lg border bg-background">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="px-3">Escalation</TableHead>
                        <TableHead>Rule</TableHead>
                        <TableHead>Target</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Next action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.escalations.map((entry) => (
                        <TableRow key={entry.escalationId}>
                          <TableCell className="px-3 align-top">
                            <p className="font-medium">{entry.escalationId}</p>
                            <p className="mt-1 max-w-[320px] text-xs leading-relaxed text-muted-foreground">
                              {entry.trigger}
                            </p>
                          </TableCell>
                          <TableCell className="align-top text-sm">
                            <p className="font-medium">{entry.rule}</p>
                            {entry.ruleLabel ? (
                              <p className="mt-1 text-xs text-muted-foreground">
                                {entry.ruleLabel}
                              </p>
                            ) : null}
                          </TableCell>
                          <TableCell className="align-top text-sm">
                            {entry.escalateTo}
                          </TableCell>
                          <TableCell className="align-top">
                            <StatusBadge
                              label={entry.status}
                              tone={
                                entry.status === "resolved"
                                  ? "success"
                                  : "destructive"
                              }
                            />
                          </TableCell>
                          <TableCell className="align-top">
                            <StatusBadge
                              label={entry.blocking ? "blocking" : "advisory"}
                              tone={entry.blocking ? "destructive" : "warning"}
                            />
                          </TableCell>
                          <TableCell className="align-top text-sm">
                            {entry.nextAction}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Audit tab */}
          <TabsContent
            ref={auditRef}
            value="audit"
            className="space-y-5 transition-all duration-200 ease-out"
          >
          <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
            <Card>
              <CardHeader>
                <CardTitle>Decision timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {data.auditTrail.timeline.map((event, index) => (
                  <div key={event.id} className="relative pl-7">
                    {index !== data.auditTrail.timeline.length - 1 ? (
                      <div className="absolute left-[9px] top-6 h-[calc(100%+0.45rem)] w-px bg-border" />
                    ) : null}
                    <div className="absolute left-0 top-1 size-5 rounded-full border bg-card" />
                    <p className="text-xs font-medium text-muted-foreground">
                      {formatDateTime(event.timestamp)}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <StatusBadge label={event.kind} tone="info" />
                      {event.level ? (
                        <StatusBadge
                          label={event.level}
                          tone={
                            event.level === "error"
                              ? "destructive"
                              : event.level === "warn"
                                ? "warning"
                                : "neutral"
                          }
                        />
                      ) : null}
                      {event.stepName ? (
                        <StatusBadge label={event.stepName} tone="neutral" />
                      ) : null}
                    </div>
                    <h3 className="mt-1 text-sm font-semibold">
                      {event.title}
                    </h3>
                    <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                      {event.description}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card className="bg-card/70">
                <CardHeader>
                  <CardTitle>Audit facts</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  <FieldCell
                    label="Policies checked"
                    value={data.auditTrail.policiesChecked.join(", ")}
                    variant="default"
                  />
                  <FieldCell
                    label="Suppliers evaluated"
                    value={data.auditTrail.supplierIdsEvaluated.join(", ")}
                    variant="default"
                  />
                  <FieldCell
                    label="Pricing tiers applied"
                    value={data.auditTrail.pricingTiersApplied}
                    variant="default"
                  />
                  <FieldCell
                    label="Data sources used"
                    value={data.auditTrail.dataSourcesUsed.join(", ")}
                    variant="default"
                  />
                  <FieldCell
                    label="Historical awards consulted"
                    value={
                      data.auditTrail.historicalAwardsConsulted ? "Yes" : "No"
                    }
                    variant="default"
                  />
                  <FieldCell
                    label="Historical award note"
                    value={data.auditTrail.historicalAwardNote}
                    variant="default"
                  />
                </CardContent>
              </Card>

              <Card className="bg-card/70">
                <CardHeader>
                  <CardTitle>Reasoning trace</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {data.auditTrail.reasoningTrace.map((step, index) => (
                    <div key={step} className="rounded-lg border bg-background/80 p-3.5">
                      <div className="flex items-center gap-1.5">
                        <StatusBadge
                          label={`Step ${index + 1}`}
                          tone="info"
                        />
                        <StatusBadge
                          label={
                            index === 0
                              ? "LLM-assisted interpretation"
                              : "Deterministic policy logic"
                          }
                          tone={index === 0 ? "info" : "neutral"}
                        />
                      </div>
                      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        {step}
                      </p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>

          <Card className="bg-muted/15">
            <CardHeader>
              <CardTitle>Advanced pipeline diagnostics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Access run diagnostics and step-level controls moved from Pipeline Ops.
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={runId}
                  onChange={(event) => setRunId(event.target.value)}
                  placeholder="Run ID (optional for run detail)"
                  className="w-full sm:w-[340px]"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRunDiagnostics}
                  disabled={loadingAction !== null}
                >
                  {loadingAction === "runs" ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Activity className="size-3.5" />
                  )}
                  List runs
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRunDetail}
                  disabled={loadingAction !== null || !runId.trim()}
                >
                  {loadingAction === "run" ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Play className="size-3.5" />
                  )}
                  Get run
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAuditTrail}
                  disabled={loadingAction !== null}
                >
                  {loadingAction === "audit" ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <ShieldCheck className="size-3.5" />
                  )}
                  Audit trail
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAuditSummary}
                  disabled={loadingAction !== null}
                >
                  {loadingAction === "summary" ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <ShieldCheck className="size-3.5" />
                  )}
                  Audit summary
                </Button>
              </div>

              <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
                {(["fetch", "validate", "filter", "comply", "rank", "escalate"] as const).map(
                  (step) => (
                    <Button
                      key={step}
                      variant="outline"
                      size="sm"
                      onClick={() => handleStep(step)}
                      disabled={loadingAction !== null}
                    >
                      {loadingAction === `step:${step}` ? (
                        <RefreshCw className="size-3.5 animate-spin" />
                      ) : (
                        <Play className="size-3.5" />
                      )}
                      {step}
                    </Button>
                  ),
                )}
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                {statusResult ? (
                  <JsonViewer title="Pipeline Status" value={statusResult} />
                ) : null}
                {pipelineResult ? (
                  <JsonViewer title="Pipeline Result" value={pipelineResult} />
                ) : null}
                {runsResult ? <JsonViewer title="Runs" value={runsResult} /> : null}
                {runDetailResult ? (
                  <JsonViewer title="Run Detail" value={runDetailResult} />
                ) : null}
                {auditResult ? (
                  <JsonViewer title="Audit Trail" value={auditResult} />
                ) : null}
                {summaryResult ? (
                  <JsonViewer title="Audit Summary" value={summaryResult} />
                ) : null}
                {stepResult ? <JsonViewer title="Step Result" value={stepResult} /> : null}
              </div>
            </CardContent>
          </Card>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}

function KpiCell({
  label,
  value,
  helper,
}: {
  label: string
  value: string | number
  helper: string
}) {
  return (
    <div className="rounded-lg border bg-card/50 p-3.5">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-base font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{helper}</p>
    </div>
  )
}

function FieldCell({
  label,
  value,
  variant = "muted",
  className,
  valueClassName,
}: {
  label: string
  value: ReactNode
  variant?: "muted" | "default" | "emphasis"
  className?: string
  valueClassName?: string
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        variant === "default" && "bg-background/80",
        variant === "muted" && "bg-muted/20",
        variant === "emphasis" && "border-primary/30 bg-primary/[0.05]",
        className,
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-1 text-sm leading-relaxed", valueClassName)}>{value}</p>
    </div>
  )
}

function MiniMetric({
  label,
  value,
  helper,
}: {
  label: string
  value: string | number
  helper: string
}) {
  return (
    <Card className="bg-card/70">
      <CardContent className="space-y-1.5 px-4 py-3.5">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className="text-xl font-semibold tabular-nums tracking-tight">
          {value}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {helper}
        </p>
      </CardContent>
    </Card>
  )
}
