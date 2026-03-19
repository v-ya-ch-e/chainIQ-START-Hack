"use client"

import { AlertTriangle, ArrowLeft, ChevronRight, Download, Loader2, Play, RefreshCw, ShieldCheck, TimerReset } from "lucide-react"
import { toast } from "sonner"
import Link from "next/link"
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"

import { SectionHeading } from "@/components/shared/section-heading"
import { JsonViewer } from "@/components/shared/json-viewer"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
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
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  displayApprovalTier,
  displayCaseStatus,
  displayRecommendationStatus,
  formatCurrency,
  formatDate,
  formatDateTime,
  scoreTone,
  severityTone,
  titleCase,
} from "@/lib/data/formatters"
import type {
  AuditTimelineEvent,
  CaseDetail,
  EvaluationRunDetail,
  RuleCheckResult,
  SupplierRuleBreakdown,
  SupplierRuleCheck,
  SupplierRow,
  ValidationIssue,
} from "@/lib/types/case"
import { useSetWorkspaceHeaderActions } from "@/components/app-shell/workspace-header-actions"
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
  initialRunId?: string
  showReturnToLatest?: boolean
}

type CaseTab = "overview" | "suppliers" | "escalations" | "audit"

function livePhaseLabel(
  phase: "idle" | "queued" | "running" | "completed" | "failed" | "unknown" | "timed_out",
) {
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

function livePhaseTone(
  phase: "idle" | "queued" | "running" | "completed" | "failed" | "unknown" | "timed_out",
) {
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

function filenameFromContentDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const utfMatch = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch?.[1]) {
    const decoded = decodeURIComponent(utfMatch[1]).trim()
    if (decoded) return decoded
  }
  const quotedMatch = header.match(/filename="([^"]+)"/i)
  if (quotedMatch?.[1]) return quotedMatch[1].trim()
  const rawMatch = header.match(/filename=([^;]+)/i)
  if (rawMatch?.[1]) return rawMatch[1].trim()
  return fallback
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function toRuleCheckResult(value: string | null | undefined): RuleCheckResult {
  if (value === "passed" || value === "failed" || value === "warned" || value === "skipped") {
    return value
  }
  return "skipped"
}

function getSupplierBreakdown(
  supplierId: string,
  runs: EvaluationRunDetail[],
  preferredRun: EvaluationRunDetail | null,
): SupplierRuleBreakdown | null {
  if (preferredRun) {
    const preferredMatch = preferredRun.supplierBreakdowns.find(
      (entry) => entry.supplierId === supplierId,
    )
    if (preferredMatch) return preferredMatch
  }

  const fallbackRuns = runs
    .filter((run) => (preferredRun ? run.runId !== preferredRun.runId : true))
    .slice()
    .sort(
      (a, b) =>
        new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
    )

  for (const run of fallbackRuns) {
    const match = run.supplierBreakdowns.find(
      (entry) => entry.supplierId === supplierId,
    )
    if (match) return match
  }

  return null
}

function meetsAllCriteria(breakdown: SupplierRuleBreakdown | null): boolean {
  if (!breakdown || breakdown.excluded) return false
  const failedHard = breakdown.hardRuleChecks.some((check) => check.result === "failed")
  const failedPolicy = breakdown.policyChecks.some((check) => check.result === "failed")
  return !failedHard && !failedPolicy
}

function CaseWorkspaceHeaderActions({
  caseId,
  showReturnToLatest,
  loadingAction,
  onRerun,
  onStatus,
  onResult,
  onExport,
  onAuditDownload,
  onEscalate,
}: {
  caseId: string
  showReturnToLatest: boolean
  loadingAction: string | null
  onRerun: () => void
  onStatus: () => void
  onResult: () => void
  onExport: () => void
  onAuditDownload: () => void
  onEscalate: () => void
}) {
  return (
    <div className="max-w-full overflow-x-auto overscroll-x-contain py-0.5 [scrollbar-width:thin]">
      <div className="ml-auto flex w-max min-w-0 flex-nowrap items-center gap-3">
      {showReturnToLatest ? (
        <Link
          href={`/cases/${caseId}`}
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            "h-8 shrink-0 gap-1.5 whitespace-nowrap",
          )}
        >
          <ArrowLeft className="size-3.5" />
          Return to latest evaluation
        </Link>
      ) : null}
      <Button
        variant="outline"
        size="sm"
        className="h-8 shrink-0"
        onClick={onRerun}
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
        className="h-8 shrink-0"
        onClick={onStatus}
        disabled={loadingAction !== null}
      >
        {loadingAction === "status" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <RefreshCw className="size-3.5" />
        )}
        {loadingAction === "status" ? "Checking..." : "Check updates"}
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-8 shrink-0"
        onClick={onResult}
        disabled={loadingAction !== null}
      >
        {loadingAction === "result" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <ShieldCheck className="size-3.5" />
        )}
        Result
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-8 shrink-0"
        onClick={onExport}
        disabled={loadingAction !== null}
      >
        {loadingAction === "export" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Download className="size-3.5" />
        )}
        {loadingAction === "export" ? "Exporting..." : "Export"}
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-8 shrink-0"
        onClick={onAuditDownload}
        disabled={loadingAction !== null}
      >
        {loadingAction === "auditDownload" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <ShieldCheck className="size-3.5" />
        )}
        {loadingAction === "auditDownload" ? "Downloading..." : "Audit"}
      </Button>
      <Button
        size="sm"
        className="h-8 shrink-0"
        onClick={onEscalate}
        disabled={loadingAction !== null}
      >
        {loadingAction === "escalate" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <TimerReset className="size-3.5" />
        )}
        {loadingAction === "escalate" ? "Escalating..." : "Escalate"}
      </Button>
      </div>
    </div>
  )
}


export function CaseWorkspace({
  data,
  initialTab = "overview",
  createdFromIntake = false,
  initialRunId,
  showReturnToLatest = false,
}: CaseWorkspaceProps) {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<CaseTab>(initialTab)
  const [contentMinHeight, setContentMinHeight] = useState<number | null>(null)
  const [runId, setRunId] = useState("")
  const [selectedRunId, setSelectedRunId] = useState<string | null>(
    initialRunId ?? data.evaluationRuns[0]?.runId ?? null,
  )
  const [suppliersExpanded, setSuppliersExpanded] = useState(false)
  const [supplierPriority, setSupplierPriority] = useState<"balanced" | "price" | "speed">("balanced")
  const [selectedSupplierDetail, setSelectedSupplierDetail] = useState<{
    supplier: SupplierRow
    breakdown: SupplierRuleBreakdown | null
  } | null>(null)
  const [selectedIssue, setSelectedIssue] = useState<ValidationIssue | null>(null)
  const [statusResult, setStatusResult] = useState<unknown>(null)
  const [pipelineResult, setPipelineResult] = useState<unknown>(null)
  const [runsResult, setRunsResult] = useState<unknown>(null)
  const [runDetailResult, setRunDetailResult] = useState<unknown>(null)
  const [auditResult, setAuditResult] = useState<unknown>(null)
  const [summaryResult, setSummaryResult] = useState<unknown>(null)
  const [stepResult, setStepResult] = useState<unknown>(null)
  const {
    loadingAction,
    runAction,
    actionLifecycleByLabel,
    lastActionLifecycle,
  } = usePipelineActionRunner()
  const { requestLiveState, startPolling, patchRequestState } =
    useRequestStatusPoller()
  const blockingIssues = data.validationIssues.filter((issue) => issue.blocking)
  const recommendedSupplier = data.recommendation.recommendedSupplier
  const activeEscalation =
    data.escalations.find((entry) => entry.status !== "resolved") ??
    data.escalations[0] ??
    null
  const selectedRun =
    data.evaluationRuns.find((run) => run.runId === selectedRunId) ??
    data.evaluationRuns[0] ??
    null
  const selectedRunOrdinal = selectedRun
    ? data.evaluationRuns.findIndex((run) => run.runId === selectedRun.runId) + 1
    : null
  const effectiveShortlist =
    selectedRun?.supplierShortlist && selectedRun.supplierShortlist.length > 0
      ? selectedRun.supplierShortlist
      : data.supplierShortlist
  const effectiveExcluded =
    selectedRun?.excludedSuppliersFromRun &&
    selectedRun.excludedSuppliersFromRun.length > 0
      ? selectedRun.excludedSuppliersFromRun
      : data.excludedSuppliers
  const evaluatedSuppliers = effectiveShortlist.length + effectiveExcluded.length
  const hasShortlist = effectiveShortlist.length > 0
  const lowestPrice = hasShortlist
    ? Math.min(...effectiveShortlist.map((entry) => entry.totalPrice))
    : null
  const fastestExpeditedLeadTime = hasShortlist
    ? Math.min(...effectiveShortlist.map((entry) => entry.expeditedLeadTimeDays))
    : null
  const overviewRef = useRef<HTMLDivElement>(null)
  const suppliersRef = useRef<HTMLDivElement>(null)
  const escalationsRef = useRef<HTMLDivElement>(null)
  const auditRef = useRef<HTMLDivElement>(null)
  const createdFlowHandledRef = useRef(false)

  const shortlistWithBreakdown = effectiveShortlist.map((s) => ({
    supplier: s,
    breakdown: getSupplierBreakdown(s.supplierId, data.evaluationRuns, selectedRun),
    meetsAll: meetsAllCriteria(
      getSupplierBreakdown(s.supplierId, data.evaluationRuns, selectedRun),
    ),
  }))
  const compliantFirst = [...shortlistWithBreakdown].sort((a, b) => {
    if (a.meetsAll !== b.meetsAll) return a.meetsAll ? -1 : 1
    if (supplierPriority === "price") return a.supplier.totalPrice - b.supplier.totalPrice
    if (supplierPriority === "speed") return a.supplier.expeditedLeadTimeDays - b.supplier.expeditedLeadTimeDays
    return 0
  })
  const compliantCount = compliantFirst.filter((x) => x.meetsAll).length
  const visibleCount = suppliersExpanded
    ? compliantFirst.length
    : compliantCount > 0
      ? Math.min(3, compliantCount)
      : Math.min(3, compliantFirst.length)
  const visibleSuppliers = compliantFirst.slice(0, visibleCount)
  const hasMore = compliantFirst.length > visibleCount

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
      toast.success("Case created successfully", { description: data.id })
    }
  }, [createdFromIntake, data.id])

  useEffect(() => {
    if (!createdFromIntake || createdFlowHandledRef.current) return
    createdFlowHandledRef.current = true

    const nextUrl = `/cases/${data.id}?tab=${activeTab}`
    const clearCreatedFlag = () => {
      router.replace(nextUrl, { scroll: false })
    }

    if (data.evaluationRuns.length > 0) {
      clearCreatedFlag()
      return
    }

    const startedAt = new Date().toISOString()
    patchRequestState(data.id, {
      phase: "queued",
      startedAt,
      lastCheckedAt: startedAt,
      finishedAt: undefined,
      error: undefined,
    })

    void runAction({
      label: "autoTrigger",
      request: () =>
        chainIqApi.pipeline.processBatch({
          request_ids: [data.id],
          concurrency: 1,
        }),
      successMessage: "Pipeline trigger started",
      successDescription: data.id,
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
        toast.warning("Case created but auto-trigger failed", {
          description: "Use Re-run to start processing manually.",
        })
      })
      .finally(() => {
        clearCreatedFlag()
      })
  }, [
    activeTab,
    createdFromIntake,
    data.evaluationRuns.length,
    data.id,
    patchRequestState,
    router,
    runAction,
    startPolling,
  ])

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
      successMessage: "Pipeline re-run started",
      successDescription: data.id,
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
      successMessage: "Status updated",
      successDescription: data.id,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleResult() {
    void runAction({
      label: "result",
      request: () => chainIqApi.pipeline.result(data.id),
      onSuccess: setPipelineResult,
      successMessage: "Pipeline result loaded",
      successDescription: data.id,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleRunDiagnostics() {
    void runAction({
      label: "runs",
      request: () => chainIqApi.pipeline.runs({ limit: 25, skip: 0 }),
      onSuccess: setRunsResult,
      successMessage: "Pipeline runs loaded",
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
      successMessage: "Run details loaded",
      successDescription: runId.trim(),
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleAuditTrail() {
    void runAction({
      label: "audit",
      request: () => chainIqApi.pipeline.audit(data.id, { limit: 100, skip: 0 }),
      onSuccess: setAuditResult,
      successMessage: "Audit trail loaded",
      successDescription: data.id,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleAuditSummary() {
    void runAction({
      label: "summary",
      request: () => chainIqApi.pipeline.auditSummary(data.id),
      onSuccess: setSummaryResult,
      successMessage: "Audit summary loaded",
      successDescription: data.id,
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
      successMessage: `Step "${step}" executed`,
      successDescription: data.id,
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
    void runAction({
      label: "export",
      request: async () => ({
        request_id: data.id,
        exported_at: new Date().toISOString(),
        case_data: data,
        pipeline: {
          status: statusResult,
          result: pipelineResult,
          runs: runsResult,
          run_detail: runDetailResult,
          audit_trail: auditResult,
          audit_summary: summaryResult,
          step_result: stepResult,
          live_state: requestLiveState[data.id] ?? null,
        },
      }),
      onSuccess: (exportPayload) => {
        const payload = JSON.stringify(exportPayload, null, 2)
        const blob = new Blob([payload], { type: "application/json" })
        downloadBlob(blob, `${data.id}-export.json`)
      },
      successMessage: "JSON export downloaded",
      successDescription: data.id,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleAuditDownload() {
    void runAction({
      label: "auditDownload",
      request: () => chainIqApi.pipeline.report(data.id),
      onSuccess: ({ blob, contentDisposition }) => {
        const filename = filenameFromContentDisposition(
          contentDisposition,
          `${data.id}-audit-report.pdf`,
        )
        downloadBlob(blob, filename)
      },
      successMessage: "Audit report downloaded",
      successDescription: data.id,
    }).catch(() => {
      // Error state is handled by shared action runner.
    })
  }

  function handleEscalate() {
    const startedAt = new Date().toISOString()
    patchRequestState(data.id, {
      phase: "running",
      startedAt,
      lastCheckedAt: startedAt,
      finishedAt: undefined,
      error: undefined,
    })
    void runAction({
      label: "escalate",
      request: () => chainIqApi.pipeline.steps.escalate({ request_id: data.id }),
      onSuccess: setStepResult,
      successMessage: "Escalation triggered",
      successDescription: data.id,
    })
      .then(async () => {
        await startPolling(data.id, {
          initialPhase: "running",
          intervalMs: 2000,
          timeoutMs: 30_000,
        })
        router.push(`/escalations?caseId=${data.id}`)
      })
      .catch(() => {
        patchRequestState(data.id, {
          phase: "failed",
          lastCheckedAt: new Date().toISOString(),
          finishedAt: new Date().toISOString(),
        })
      })
  }

  const requestLive = requestLiveState[data.id]
  const isRerunning =
    requestLive?.phase === "queued" || requestLive?.phase === "running"
  const activeActionLifecycle = loadingAction
    ? actionLifecycleByLabel[loadingAction] ?? null
    : null

  const setHeaderActions = useSetWorkspaceHeaderActions()

  useLayoutEffect(
    () => {
      setHeaderActions(
        <CaseWorkspaceHeaderActions
          caseId={data.id}
          showReturnToLatest={showReturnToLatest}
          loadingAction={loadingAction}
          onRerun={handleRerun}
          onStatus={handleStatus}
          onResult={handleResult}
          onExport={handleExport}
          onAuditDownload={handleAuditDownload}
          onEscalate={handleEscalate}
        />,
      )
      return () => setHeaderActions(null)
    },
    // Toolbar uses current handler closures; listed deps cover case refresh and busy state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setHeaderActions, data, showReturnToLatest, loadingAction],
  )

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="animate-fade-in-up space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge
            label={displayCaseStatus(data.rawRequest.status)}
            tone="neutral"
          />
          <StatusBadge
            label={displayRecommendationStatus(data.recommendation.status)}
            tone={
              data.recommendation.status === "not_evaluated"
                ? "neutral"
                : data.recommendation.status === "proceed"
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
          title={
            showReturnToLatest && selectedRunOrdinal
              ? `${data.title} - Evaluation ${selectedRunOrdinal}`
              : data.title
          }
          description={
            showReturnToLatest && selectedRun
              ? `${data.rawRequest.country} · ${data.rawRequest.businessUnit} · created ${formatDateTime(data.rawRequest.createdAt)} · required by ${formatDate(data.rawRequest.requiredByDate)} · run ${formatDateTime(selectedRun.startedAt)}`
              : `${data.rawRequest.country} · ${data.rawRequest.businessUnit} · created ${formatDateTime(data.rawRequest.createdAt)} · required by ${formatDate(data.rawRequest.requiredByDate)}`
          }
        />

        <div className="flex flex-nowrap items-center gap-2">
          {showReturnToLatest ? (
            <Link
              href={`/cases/${data.id}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1.5")}
            >
              <ArrowLeft className="size-3.5" />
              Return to latest evaluation
            </Link>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRerun}
            disabled={isRerunning}
          >
            {isRerunning ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Play className="size-3.5" />
            )}
            Re-run
          </Button>
          <Button variant="outline" size="sm">
            <Download className="size-3.5" />
            Export
          </Button>
          <Button variant="outline" size="sm">
            <ShieldCheck className="size-3.5" />
            Audit
          </Button>
          <Button size="sm" onClick={handleEscalate}>
            <TimerReset className="size-3.5" />
            Escalate
          </Button>
        </div>
      </div>

      {requestLive && (requestLive.phase === "queued" || requestLive.phase === "running") ? (
        <Card className="border-blue-200 bg-blue-50/60">
          <CardContent className="flex items-center gap-3 py-3">
            <Loader2 className="size-4 animate-spin text-blue-700" />
            <p className="text-sm font-medium text-blue-800">
              Pipeline is {livePhaseLabel(requestLive.phase).toLowerCase()}…
            </p>
          </CardContent>
        </Card>
      ) : null}

      {/* Primary summary strip */}
      <section className="animate-fade-in-up grid gap-4 xl:grid-cols-[1.2fr_0.8fr]" style={{ animationDelay: "80ms" }}>
        <Card className="border-primary/20 bg-primary/[0.03]">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <StatusBadge
                label={data.outcomeLabel}
                tone={
                  data.recommendation.status === "not_evaluated"
                    ? "neutral"
                    : data.recommendation.status === "proceed"
                      ? "success"
                      : "destructive"
                }
              />
              <StatusBadge
                label={displayApprovalTier(data.recommendation.approvalTier)}
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
              label="Budget"
              value={formatCurrency(
                data.rawRequest.budgetAmount,
                data.rawRequest.currency,
              )}
              variant="default"
            />
            <FieldCell
              label="Approval Tier"
              value={displayApprovalTier(data.recommendation.approvalTier)}
            />
            <FieldCell
              label="Quotes Required"
              value={`${data.recommendation.quotesRequired}`}
            />
            <FieldCell
              label="Countries"
              value={data.rawRequest.deliveryCountries.join(", ")}
            />
            <FieldCell
              label="Scenario"
              value={data.rawRequest.scenarioTags.join(", ") || "—"}
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
                    label="Business unit"
                    value={data.rawRequest.businessUnit}
                  />
                  <FieldCell label="Site" value={data.rawRequest.site} />
                  <FieldCell
                    label="Request channel"
                    value={data.rawRequest.requestChannel}
                  />
                  <FieldCell
                    label="Language"
                    value={data.rawRequest.requestLanguage}
                  />
                  <FieldCell
                    label="Requester role"
                    value={data.rawRequest.requesterRole}
                  />
                  <FieldCell
                    label="Contract type"
                    value={data.rawRequest.contractTypeRequested}
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
                  <button
                    key={issue.issueKey}
                    type="button"
                    onClick={() => setSelectedIssue(issue)}
                    className="w-full rounded-lg border bg-background/80 p-3.5 text-left transition-colors hover:border-primary/40 hover:bg-accent/40"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <StatusBadge label={issue.issueId} tone="neutral" />
                      <StatusBadge
                        label={titleCase(issue.severity)}
                        tone={severityTone(issue.severity)}
                      />
                      <StatusBadge
                        label={titleCase(issue.type)}
                        tone="info"
                      />
                      {issue.blocking ? (
                        <StatusBadge label="Blocking" tone="destructive" />
                      ) : null}
                      <ChevronRight className="ml-auto size-4 text-muted-foreground" />
                    </div>
                    <p className="mt-2 text-sm leading-relaxed">
                      {issue.description}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      {issue.actionRequired}
                    </p>
                  </button>
                ))}
              </CardContent>
            </Card>

            <Sheet
              open={!!selectedIssue}
              onOpenChange={(open) => !open && setSelectedIssue(null)}
            >
              <SheetContent
                side="right"
                className="data-[side=right]:w-full data-[side=right]:sm:max-w-2xl overflow-y-auto px-6"
              >
                <SheetHeader>
                  <SheetTitle className="flex items-center gap-2">
                    <AlertTriangle className="size-4" />
                    {selectedIssue?.issueId ?? "Issue"}
                  </SheetTitle>
                  <SheetDescription>
                    Validation issue details, audit log context, and related pipeline events.
                  </SheetDescription>
                </SheetHeader>
                {selectedIssue ? (
                  <IssueDetailSheetContent
                    issue={selectedIssue}
                    requestId={data.id}
                    timeline={data.auditTrail.timeline}
                  />
                ) : null}
              </SheetContent>
            </Sheet>

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
                        label={titleCase(policy.status)}
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
                value={effectiveShortlist.length}
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
                <CardHeader className="flex-row items-center justify-between gap-4">
                  <CardTitle>Supplier comparison</CardTitle>
                  <div className="flex items-center gap-1 rounded-lg border bg-muted/30 p-0.5">
                    {(["balanced", "price", "speed"] as const).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => setSupplierPriority(mode)}
                        className={cn(
                          "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                          supplierPriority === mode
                            ? "bg-background text-foreground shadow-sm"
                            : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {mode === "balanced" ? "Balanced" : mode === "price" ? "Lowest price" : "Fastest delivery"}
                      </button>
                    ))}
                  </div>
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
                          <TableHead>Rules</TableHead>
                          <TableHead>Policy</TableHead>
                          <TableHead>Quality</TableHead>
                          <TableHead>Risk</TableHead>
                          <TableHead>ESG</TableHead>
                          <TableHead>Flags</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {visibleSuppliers.map(({ supplier }) => (
                          <TableRow
                            key={supplier.supplierId}
                            className={cn(
                              supplier.rank === 1 ? "bg-emerald-50/40" : "",
                              "[&>td]:align-top",
                            )}
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
                            <TableCell className="max-w-sm whitespace-normal break-words align-top">
                              <div className="space-y-1">
                                <p className="font-medium">
                                  {supplier.supplierName}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {supplier.countryHq ?? "N/A"} ·{" "}
                                  {supplier.currency ?? data.recommendation.currency}
                                </p>
                                {supplier.recommendationNote ? (
                                  <p className="text-xs leading-relaxed text-muted-foreground">
                                    {supplier.recommendationNote}
                                  </p>
                                ) : null}
                              </div>
                            </TableCell>
                            <TableCell className="whitespace-normal text-sm">
                              <p>{supplier.pricingTierApplied}</p>
                              <p className="text-xs text-muted-foreground">
                                {supplier.region ?? "N/A"} · qty{" "}
                                {supplier.minQuantity ?? "?"}-{supplier.maxQuantity ?? "?"}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                MOQ {supplier.moq ?? "N/A"}
                              </p>
                            </TableCell>
                            <TableCell className="whitespace-normal font-medium tabular-nums">
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
                            <TableCell className="whitespace-normal tabular-nums">
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
                            <TableCell className="whitespace-normal">
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
                  {hasMore ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSuppliersExpanded(true)}
                      className="w-full"
                    >
                      Extend — show {compliantFirst.length - visibleCount} more
                    </Button>
                  ) : null}
                </CardContent>
              </Card>

              <Sheet
                open={!!selectedSupplierDetail}
                onOpenChange={(open) => !open && setSelectedSupplierDetail(null)}
              >
                <SheetContent
                  side="right"
                  className="data-[side=right]:w-full data-[side=right]:sm:max-w-2xl overflow-y-auto px-6"
                >
                  <SheetHeader>
                    <SheetTitle>
                      {selectedSupplierDetail?.supplier.supplierName ?? "Supplier"}
                    </SheetTitle>
                    <SheetDescription>
                      Rule and policy check results for this supplier.
                    </SheetDescription>
                  </SheetHeader>
                  {selectedSupplierDetail ? (
                    <SupplierDetailSheetContent
                      requestId={data.id}
                      supplier={selectedSupplierDetail.supplier}
                      breakdown={selectedSupplierDetail.breakdown}
                    />
                  ) : null}
                </SheetContent>
              </Sheet>

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
                    {effectiveExcluded.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        No supplier was excluded.
                      </p>
                    ) : (
                      effectiveExcluded.map((supplier) => (
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
                      ))
                    )}
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

            <section className="space-y-4">
              <Card className="bg-card/70">
                <CardHeader>
                  <CardTitle>Rule checks by supplier</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {data.evaluationRuns.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No stored evaluation runs found for this case yet.
                    </p>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge
                          label={`Runs: ${data.evaluationRuns.length}`}
                          tone="neutral"
                        />
                        <div className="flex flex-wrap gap-2">
                          {data.evaluationRuns.slice(0, 4).map((run) => (
                            <Button
                              key={run.runId}
                              type="button"
                              size="sm"
                              variant={run.runId === selectedRun?.runId ? "default" : "outline"}
                              onClick={() => setSelectedRunId(run.runId)}
                            >
                              {run.runId.slice(0, 8)}
                            </Button>
                          ))}
                          {data.evaluationRuns.length > 4 ? (
                            <StatusBadge label="More in API" tone="info" />
                          ) : null}
                        </div>
                      </div>

                      {selectedRun ? (
                        <EvaluationRunBreakdown run={selectedRun} />
                      ) : null}
                    </>
                  )}
                </CardContent>
              </Card>
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
                      <StatusBadge label={activeEscalation.rule} tone="info" />
                      <StatusBadge
                        label={titleCase(activeEscalation.status)}
                        tone={
                          activeEscalation.status === "resolved"
                            ? "success"
                            : "destructive"
                        }
                      />
                      <StatusBadge
                        label={activeEscalation.blocking ? "Blocking" : "Advisory"}
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
                            <p className="font-medium">{entry.ruleLabel || entry.rule}</p>
                            <p className="mt-1 max-w-[320px] text-xs leading-relaxed text-muted-foreground">
                              {entry.trigger}
                            </p>
                          </TableCell>
                          <TableCell className="align-top text-sm">
                            <StatusBadge label={entry.rule} tone="info" />
                          </TableCell>
                          <TableCell className="align-top text-sm">
                            {entry.escalateTo}
                          </TableCell>
                          <TableCell className="align-top">
                            <StatusBadge
                              label={titleCase(entry.status)}
                              tone={
                                entry.status === "resolved"
                                  ? "success"
                                  : "destructive"
                              }
                            />
                          </TableCell>
                          <TableCell className="align-top">
                            <StatusBadge
                              label={entry.blocking ? "Blocking" : "Advisory"}
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
                      <StatusBadge label={titleCase(event.kind)} tone="info" />
                      {event.level ? (
                        <StatusBadge
                          label={titleCase(event.level)}
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
                    label="Suppliers evaluated"
                    value={
                      data.auditTrail.supplierIdsEvaluated
                        .map((id) => {
                          const match = data.supplierShortlist.find((s) => s.supplierId === id)
                            ?? data.excludedSuppliers.find((s) => s.supplierId === id)
                          return match?.supplierName ?? id
                        })
                        .join(", ") || "—"
                    }
                    variant="default"
                  />
                  <FieldCell
                    label="Policies checked"
                    value={`${data.auditTrail.policiesChecked.length} rules`}
                    variant="default"
                  />
                  <FieldCell
                    label="Pricing tiers applied"
                    value={data.auditTrail.pricingTiersApplied}
                    variant="default"
                  />
                  <FieldCell
                    label="Historical precedent"
                    value={
                      data.auditTrail.historicalAwardsConsulted
                        ? data.auditTrail.historicalAwardNote || "Yes"
                        : "No historical awards consulted"
                    }
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
                    <div key={`${index}-${step}`} className="rounded-lg border bg-background/80 p-3.5">
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

          <details className="group">
            <summary className="flex cursor-pointer items-center gap-2 rounded-lg border bg-muted/15 px-5 py-3 text-sm font-medium text-muted-foreground hover:text-foreground">
              <ChevronRight className="size-4 transition-transform group-open:rotate-90" />
              Advanced pipeline diagnostics
            </summary>
            <Card className="mt-2 bg-muted/15 border-dashed">
              <CardContent className="space-y-4 pt-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    value={runId}
                    onChange={(event) => setRunId(event.target.value)}
                    placeholder="Run ID (optional for run detail)"
                    className="w-full sm:w-[340px]"
                  />
                  <Button variant="outline" size="sm" onClick={handleRunDiagnostics} disabled={loadingAction !== null}>
                    {loadingAction === "runs" ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
                    List runs
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleRunDetail} disabled={loadingAction !== null || !runId.trim()}>
                    {loadingAction === "run" ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                    Get run
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleAuditTrail} disabled={loadingAction !== null}>
                    {loadingAction === "audit" ? <Loader2 className="size-3.5 animate-spin" /> : <ShieldCheck className="size-3.5" />}
                    Audit trail
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleAuditSummary} disabled={loadingAction !== null}>
                    {loadingAction === "summary" ? <Loader2 className="size-3.5 animate-spin" /> : <ShieldCheck className="size-3.5" />}
                    Audit summary
                  </Button>
                </div>
                <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
                  {(["fetch", "validate", "filter", "comply", "rank", "escalate"] as const).map((step) => (
                    <Button key={step} variant="outline" size="sm" onClick={() => handleStep(step)} disabled={loadingAction !== null}>
                      {loadingAction === `step:${step}` ? <RefreshCw className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                      {step}
                    </Button>
                  ))}
                </div>
                <div className="grid gap-4 xl:grid-cols-2">
                  {statusResult ? <JsonViewer title="Pipeline Status" value={statusResult} /> : null}
                  {pipelineResult ? <JsonViewer title="Pipeline Result" value={pipelineResult} /> : null}
                  {runsResult ? <JsonViewer title="Runs" value={runsResult} /> : null}
                  {runDetailResult ? <JsonViewer title="Run Detail" value={runDetailResult} /> : null}
                  {auditResult ? <JsonViewer title="Audit Trail" value={auditResult} /> : null}
                  {summaryResult ? <JsonViewer title="Audit Summary" value={summaryResult} /> : null}
                  {stepResult ? <JsonViewer title="Step Result" value={stepResult} /> : null}
                </div>
              </CardContent>
            </Card>
          </details>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}

function toneForCheckResult(result: SupplierRuleCheck["result"]) {
  if (result === "passed") return "success"
  if (result === "warned") return "warning"
  if (result === "skipped") return "neutral"
  return "destructive"
}

function SupplierDetailSheetContent({
  requestId,
  supplier,
  breakdown,
}: {
  requestId: string
  supplier: SupplierRow
  breakdown: SupplierRuleBreakdown | null
}) {
  const [fetchedBreakdown, setFetchedBreakdown] =
    useState<SupplierRuleBreakdown | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const effectiveBreakdown = breakdown ?? fetchedBreakdown

  useEffect(() => {
    if (breakdown || !requestId || !supplier.supplierId) {
      setFetchedBreakdown(null)
      setFetchError(null)
      return
    }
    let cancelled = false
    setIsLoading(true)
    setFetchError(null)
    Promise.all([
      fetch(
        `/api/rule-versions/hard-rule-checks?request_id=${encodeURIComponent(requestId)}&supplier_id=${encodeURIComponent(supplier.supplierId)}`,
      ).then((r) => (r.ok ? r.json() : [])),
      fetch(
        `/api/rule-versions/policy-checks?request_id=${encodeURIComponent(requestId)}&supplier_id=${encodeURIComponent(supplier.supplierId)}`,
      ).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([hardChecks, policyChecks]) => {
        if (cancelled) return
        const h = Array.isArray(hardChecks) ? hardChecks : []
        const p = Array.isArray(policyChecks) ? policyChecks : []
        if (h.length === 0 && p.length === 0) {
          setFetchedBreakdown(null)
          return
        }
        setFetchedBreakdown({
          supplierId: supplier.supplierId,
          supplierName: supplier.supplierName,
          excluded: false,
          exclusionRuleId: null,
          exclusionReason: null,
          hardRuleChecks: h.map((c: { check_id: string; rule_id: string; version_id: string; supplier_id: string | null; result: string; skipped?: boolean; checked_at: string }) => ({
            checkId: c.check_id,
            ruleId: c.rule_id,
            versionId: c.version_id,
            supplierId: c.supplier_id,
            result: c.skipped ? "skipped" : toRuleCheckResult(c.result),
            checkedAt: c.checked_at,
          })),
          policyChecks: p.map((c: { check_id: string; rule_id: string; version_id: string; supplier_id: string | null; result: string; checked_at: string }) => ({
            checkId: c.check_id,
            ruleId: c.rule_id,
            versionId: c.version_id,
            supplierId: c.supplier_id,
            result: toRuleCheckResult(c.result),
            checkedAt: c.checked_at,
          })),
        })
      })
      .catch((err) => {
        if (!cancelled) setFetchError(err instanceof Error ? err.message : "Failed to load checks")
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [requestId, supplier.supplierId, supplier.supplierName, breakdown])

  if (isLoading && !effectiveBreakdown) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading rule checks…
      </div>
    )
  }

  if (fetchError && !effectiveBreakdown) {
    return (
      <p className="text-sm text-destructive">
        Could not load checks: {fetchError}
      </p>
    )
  }

  if (!effectiveBreakdown) {
    return (
      <p className="text-sm text-muted-foreground">
        No evaluation run data found for this supplier.
      </p>
    )
  }

  const hardPassed = effectiveBreakdown.hardRuleChecks
    .filter((c) => c.result === "passed")
    .map((c) => c.ruleId)
  const policyPassed = effectiveBreakdown.policyChecks
    .filter((c) => c.result === "passed")
    .map((c) => c.ruleId)

  return (
    <div className="space-y-6 pt-4 pb-6">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge label={supplier.supplierId} tone="neutral" />
        <StatusBadge
          label={`Hard: ${hardPassed.length}/${effectiveBreakdown.hardRuleChecks.length}`}
          tone={
            effectiveBreakdown.hardRuleChecks.some((c) => c.result === "failed")
              ? "destructive"
              : "neutral"
          }
        />
        <StatusBadge
          label={`Policy: ${policyPassed.length}/${effectiveBreakdown.policyChecks.length}`}
          tone={
            effectiveBreakdown.policyChecks.some((c) => c.result === "failed")
              ? "destructive"
              : effectiveBreakdown.policyChecks.some((c) => c.result === "warned")
                ? "warning"
                : "neutral"
          }
        />
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Hard checks
          </p>
          {hardPassed.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              Rules passed: {hardPassed.join(", ")}
            </p>
          ) : null}
          <div className="overflow-x-auto rounded-lg border p-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="px-3 py-3">Rule</TableHead>
                  <TableHead className="py-3">Version</TableHead>
                  <TableHead className="py-3">Result</TableHead>
                  <TableHead className="py-3">Checked</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {effectiveBreakdown.hardRuleChecks.map((check) => (
                  <TableRow key={check.checkId}>
                    <TableCell className="px-3 py-3 font-medium">{check.ruleId}</TableCell>
                    <TableCell className="py-3 text-xs text-muted-foreground">
                      {check.versionId.slice(0, 8)}
                    </TableCell>
                    <TableCell className="py-3">
                      <StatusBadge
                        label={titleCase(check.result)}
                        tone={toneForCheckResult(check.result)}
                      />
                    </TableCell>
                    <TableCell className="py-3 text-xs text-muted-foreground">
                      {formatDateTime(check.checkedAt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Policy checks
          </p>
          {policyPassed.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              Rules passed: {policyPassed.join(", ")}
            </p>
          ) : null}
          <div className="overflow-x-auto rounded-lg border p-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="px-3 py-3">Rule</TableHead>
                  <TableHead className="py-3">Version</TableHead>
                  <TableHead className="py-3">Result</TableHead>
                  <TableHead className="py-3">Checked</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {effectiveBreakdown.policyChecks.map((check) => (
                  <TableRow key={check.checkId}>
                    <TableCell className="px-3 py-3 font-medium">{check.ruleId}</TableCell>
                    <TableCell className="py-3 text-xs text-muted-foreground">
                      {check.versionId.slice(0, 8)}
                    </TableCell>
                    <TableCell className="py-3">
                      <StatusBadge
                        label={titleCase(check.result)}
                        tone={toneForCheckResult(check.result)}
                      />
                    </TableCell>
                    <TableCell className="py-3 text-xs text-muted-foreground">
                      {formatDateTime(check.checkedAt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </div>
  )
}

function EvaluationRunBreakdown({ run }: { run: EvaluationRunDetail }) {
  const suppliers = run.supplierBreakdowns
    .slice()
    .sort((a, b) => (a.excluded === b.excluded ? 0 : a.excluded ? 1 : -1))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge label={`Run ${run.runId}`} tone="neutral" />
        <StatusBadge label={titleCase(run.status)} tone="info" />
        <StatusBadge label={`Suppliers ${suppliers.length}`} tone="neutral" />
      </div>

      <div className="space-y-4">
        {suppliers.map((supplier) => {
          const passedHard = supplier.hardRuleChecks.filter((c) => c.result === "passed").length
          const failedHard = supplier.hardRuleChecks.filter((c) => c.result === "failed").length
          const skippedHard = supplier.hardRuleChecks.filter((c) => c.result === "skipped").length

          const passedPolicy = supplier.policyChecks.filter((c) => c.result === "passed").length
          const warnedPolicy = supplier.policyChecks.filter((c) => c.result === "warned").length
          const failedPolicy = supplier.policyChecks.filter((c) => c.result === "failed").length

          return (
            <div key={supplier.supplierId} className="rounded-lg border bg-background/80 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <StatusBadge label={supplier.supplierId} tone="neutral" />
                    {supplier.excluded ? (
                      <StatusBadge label="excluded" tone="destructive" />
                    ) : (
                      <StatusBadge label="evaluated" tone="success" />
                    )}
                  </div>
                  <p className="text-sm font-semibold">
                    {supplier.supplierName ?? "Supplier"}
                  </p>
                  {supplier.exclusionReason ? (
                    <p className="text-sm text-muted-foreground">
                      {supplier.exclusionRuleId ? `${supplier.exclusionRuleId}: ` : ""}
                      {supplier.exclusionReason}
                    </p>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2">
                  <StatusBadge
                    label={`Hard: ${passedHard}✓ ${failedHard}✕ ${skippedHard}⎯`}
                    tone={failedHard > 0 ? "destructive" : "neutral"}
                  />
                  <StatusBadge
                    label={`Policy: ${passedPolicy}✓ ${warnedPolicy}⚠ ${failedPolicy}✕`}
                    tone={failedPolicy > 0 ? "destructive" : warnedPolicy > 0 ? "warning" : "neutral"}
                  />
                </div>
              </div>

              <Separator className="my-4" />

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Hard checks
                  </p>
                  <div className="overflow-x-auto rounded-lg border p-4">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="px-3 py-3">Rule</TableHead>
                          <TableHead className="py-3">Version</TableHead>
                          <TableHead className="py-3">Result</TableHead>
                          <TableHead className="py-3">Checked</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {supplier.hardRuleChecks.map((check) => (
                          <TableRow key={check.checkId}>
                            <TableCell className="px-3 py-3 font-medium">{check.ruleId}</TableCell>
                            <TableCell className="py-3 text-xs text-muted-foreground">
                              {check.versionId.slice(0, 8)}
                            </TableCell>
                            <TableCell className="py-3">
                              <StatusBadge label={titleCase(check.result)} tone={toneForCheckResult(check.result)} />
                            </TableCell>
                            <TableCell className="py-3 text-xs text-muted-foreground">
                              {formatDateTime(check.checkedAt)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Policy checks
                  </p>
                  <div className="overflow-x-auto rounded-lg border p-4">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="px-3 py-3">Rule</TableHead>
                          <TableHead className="py-3">Version</TableHead>
                          <TableHead className="py-3">Result</TableHead>
                          <TableHead className="py-3">Checked</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {supplier.policyChecks.map((check) => (
                          <TableRow key={check.checkId}>
                            <TableCell className="px-3 py-3 font-medium">{check.ruleId}</TableCell>
                            <TableCell className="py-3 text-xs text-muted-foreground">
                              {check.versionId.slice(0, 8)}
                            </TableCell>
                            <TableCell className="py-3">
                              <StatusBadge label={titleCase(check.result)} tone={toneForCheckResult(check.result)} />
                            </TableCell>
                            <TableCell className="py-3 text-xs text-muted-foreground">
                              {formatDateTime(check.checkedAt)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
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

function IssueDetailSheetContent({
  issue,
  requestId,
  timeline,
}: {
  issue: ValidationIssue
  requestId: string
  timeline: AuditTimelineEvent[]
}) {
  const [relatedLogs, setRelatedLogs] = useState<AuditTimelineEvent[] | null>(null)
  const [loadingLogs, setLoadingLogs] = useState(false)
  const [logError, setLogError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchRelated() {
      setLoadingLogs(true)
      setLogError(null)
      try {
        const params: { limit?: number; skip?: number; run_id?: string; step_name?: string } = { limit: 100, skip: 0 }
        if (issue.runId) params.run_id = issue.runId
        if (issue.stepName) params.step_name = issue.stepName

        const result = await chainIqApi.orgLogs.audit.byRequest(requestId, params)
        if (cancelled) return
        const mapped = result.items.map((entry) => ({
          id: `${entry.request_id}-${entry.id}`,
          timestamp: entry.timestamp,
          title: entry.message,
          description: entry.step_name
            ? `${entry.category} · ${entry.step_name}`
            : entry.category,
          kind: "audit" as const,
          level: entry.level,
          category: entry.category,
          stepName: entry.step_name,
          source: entry.source,
          details: entry.details as Record<string, unknown> | null,
        }))
        setRelatedLogs(mapped)
      } catch (error) {
        if (cancelled) return
        setLogError(error instanceof Error ? error.message : "Failed to load related logs")
        const fromTimeline = timeline.filter(
          (event) =>
            event.category === issue.type ||
            event.stepName === issue.stepName,
        )
        setRelatedLogs(fromTimeline.length > 0 ? fromTimeline : null)
      } finally {
        if (!cancelled) setLoadingLogs(false)
      }
    }

    void fetchRelated()
    return () => { cancelled = true }
  }, [issue.runId, issue.stepName, issue.type, requestId, timeline])

  const detailEntries = issue.details
    ? Object.entries(issue.details).filter(
        ([key]) => !["action_required"].includes(key),
      )
    : []

  return (
    <div className="space-y-6 pt-4">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge label={issue.issueId} tone="neutral" />
          <StatusBadge label={titleCase(issue.severity)} tone={severityTone(issue.severity)} />
          <StatusBadge label={titleCase(issue.type)} tone="info" />
          {issue.blocking ? (
            <StatusBadge label="Blocking" tone="destructive" />
          ) : null}
        </div>

        <div className="space-y-1.5">
          <p className="text-sm font-medium leading-relaxed">{issue.description}</p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {issue.actionRequired}
          </p>
        </div>
      </div>

      <Separator />

      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Audit record
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <FieldCell label="Audit Row ID" value={String(issue.auditRowId)} variant="muted" />
          <FieldCell label="Run ID" value={issue.runId ?? "—"} variant="muted" />
          <FieldCell label="Timestamp" value={formatDateTime(issue.timestamp)} variant="muted" />
          <FieldCell label="Step" value={issue.stepName ?? "—"} variant="muted" />
          <FieldCell label="Level" value={issue.level} variant="muted" />
          <FieldCell label="Source" value={issue.source} variant="muted" />
        </div>
      </div>

      {detailEntries.length > 0 ? (
        <>
          <Separator />
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Issue details
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {detailEntries.map(([key, value]) => (
                <FieldCell
                  key={key}
                  label={titleCase(key)}
                  value={
                    typeof value === "object" && value !== null
                      ? JSON.stringify(value, null, 2)
                      : String(value ?? "—")
                  }
                  variant="muted"
                />
              ))}
            </div>
          </div>
        </>
      ) : null}

      <Separator />

      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Related audit logs{issue.stepName ? ` · ${issue.stepName}` : ""}
        </p>

        {loadingLogs ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading related logs...
          </div>
        ) : logError && !relatedLogs ? (
          <p className="text-sm text-muted-foreground">{logError}</p>
        ) : relatedLogs && relatedLogs.length > 0 ? (
          <div className="space-y-2">
            {relatedLogs.map((event) => (
              <div
                key={event.id}
                className="rounded-lg border bg-muted/20 p-3"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  {event.level ? (
                    <StatusBadge
                      label={titleCase(event.level)}
                      tone={
                        event.level === "error"
                          ? "destructive"
                          : event.level === "warning"
                            ? "warning"
                            : "neutral"
                      }
                    />
                  ) : null}
                  {event.category ? (
                    <StatusBadge
                      label={titleCase(event.category)}
                      tone="info"
                    />
                  ) : null}
                  <span className="ml-auto text-xs text-muted-foreground">
                    {formatDateTime(event.timestamp)}
                  </span>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed">{event.title}</p>
                {event.details && Object.keys(event.details).length > 0 ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
                      Raw details
                    </summary>
                    <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted/30 p-2 text-xs leading-relaxed">
                      {JSON.stringify(event.details, null, 2)}
                    </pre>
                  </details>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No related audit logs found for this step.
          </p>
        )}
      </div>
    </div>
  )
}
