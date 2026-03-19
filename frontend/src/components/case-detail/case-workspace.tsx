"use client"

import { ArrowLeft, Download, Loader2, Play, ShieldCheck, TimerReset } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState, type ReactNode } from "react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  formatCurrency,
  formatDate,
  formatDateDdMmYyyy,
  formatDateTime,
  scoreTone,
  severityTone,
} from "@/lib/data/formatters"
import type {
  CaseDetail,
  EvaluationRunDetail,
  RuleCheckResult,
  SupplierRuleBreakdown,
  SupplierRuleCheck,
  SupplierRow,
} from "@/lib/types/case"
import { cn } from "@/lib/utils"

interface CaseWorkspaceProps {
  data: CaseDetail
  initialTab?: CaseTab
  /** When provided, pre-select this run (e.g. from /cases/eval/[runId] page). */
  initialRunId?: string
  /** When true, show "Return to latest decision" button linking to case page. */
  showReturnToLatest?: boolean
}

type CaseTab = "overview" | "suppliers" | "escalations" | "audit"

function getSupplierBreakdown(
  supplierId: string,
  evaluationRuns: EvaluationRunDetail[],
  selectedRun: EvaluationRunDetail | null,
): SupplierRuleBreakdown | null {
  const run = selectedRun ?? evaluationRuns[0]
  if (!run) return null
  return run.supplierBreakdowns.find((b) => b.supplierId === supplierId) ?? null
}

function meetsAllCriteria(breakdown: SupplierRuleBreakdown | null): boolean {
  if (!breakdown) return false
  const hasFailedHard = breakdown.hardRuleChecks.some((c) => c.result === "failed")
  const hasFailedPolicy = breakdown.policyChecks.some((c) => c.result === "failed")
  return !hasFailedHard && !hasFailedPolicy
}

function getRuleCounts(breakdown: SupplierRuleBreakdown | null) {
  if (!breakdown)
    return { hardPassed: 0, hardTotal: 0, policyPassed: 0, policyTotal: 0 }
  const hardTotal = breakdown.hardRuleChecks.length
  const hardPassed = breakdown.hardRuleChecks.filter((c) => c.result === "passed").length
  const policyTotal = breakdown.policyChecks.length
  const policyPassed = breakdown.policyChecks.filter((c) => c.result === "passed").length
  return { hardPassed, hardTotal, policyPassed, policyTotal }
}

export function CaseWorkspace({
  data,
  initialTab = "overview",
  initialRunId,
  showReturnToLatest = false,
}: CaseWorkspaceProps) {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<CaseTab>(initialTab)
  const [contentMinHeight, setContentMinHeight] = useState<number | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(
    initialRunId ?? data.evaluationRuns[0]?.runId ?? null,
  )
  const [suppliersExpanded, setSuppliersExpanded] = useState(false)
  const [selectedSupplierDetail, setSelectedSupplierDetail] = useState<{
    supplier: SupplierRow
    breakdown: SupplierRuleBreakdown | null
  } | null>(null)
  const [isRerunning, setIsRerunning] = useState(false)
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

  // On the main case details page, always keep the selected run in sync
  // with the latest evaluation run after a re-run (router.refresh).
  const latestRunId = data.evaluationRuns[0]?.runId ?? null
  useEffect(() => {
    if (!showReturnToLatest) {
      setSelectedRunId(latestRunId)
    }
  }, [latestRunId, showReturnToLatest])
  const effectiveShortlist =
    selectedRun?.supplierShortlist && selectedRun.supplierShortlist.length > 0
      ? selectedRun.supplierShortlist
      : data.supplierShortlist
  const effectiveExcluded =
    selectedRun?.excludedSuppliersFromRun && selectedRun.excludedSuppliersFromRun.length > 0
      ? selectedRun.excludedSuppliersFromRun
      : data.excludedSuppliers
  const effectiveEvaluatedCount = effectiveShortlist.length + effectiveExcluded.length
  const effectiveLowestPrice =
    effectiveShortlist.length > 0
      ? Math.min(...effectiveShortlist.map((entry) => entry.totalPrice))
      : null
  const effectiveFastestExpedited =
    effectiveShortlist.length > 0
      ? Math.min(...effectiveShortlist.map((entry) => entry.expeditedLeadTimeDays))
      : null
  const overviewRef = useRef<HTMLDivElement>(null)
  const suppliersRef = useRef<HTMLDivElement>(null)
  const escalationsRef = useRef<HTMLDivElement>(null)
  const auditRef = useRef<HTMLDivElement>(null)

  async function handleRerun() {
    if (isRerunning) return
    setIsRerunning(true)
    try {
      const res = await fetch("/api/pipeline/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: data.id }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        const detail = err.detail
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || `HTTP ${res.status}`
              : `HTTP ${res.status}`
        throw new Error(msg)
      }
      router.refresh()
    } catch (err) {
      console.error("Re-run failed:", err)
      alert(err instanceof Error ? err.message : "Re-run failed. Check console.")
    } finally {
      setIsRerunning(false)
    }
  }

  const shortlistWithBreakdown = effectiveShortlist.map((s) => ({
    supplier: s,
    breakdown: getSupplierBreakdown(s.supplierId, data.evaluationRuns, selectedRun),
    meetsAll: meetsAllCriteria(
      getSupplierBreakdown(s.supplierId, data.evaluationRuns, selectedRun),
    ),
  }))
  const compliantFirst = [...shortlistWithBreakdown].sort((a, b) =>
    a.meetsAll === b.meetsAll ? 0 : a.meetsAll ? -1 : 1,
  )
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
            title={
              showReturnToLatest && selectedRun
                ? (() => {
                    const idx = data.evaluationRuns.findIndex(
                      (r) => r.runId === selectedRun.runId,
                    )
                    if (idx >= 0) {
                      return `${data.title} - Evaluation ${idx + 1}`
                    }
                    return data.title
                  })()
                : data.title
            }
            description={
              showReturnToLatest && selectedRun
                ? `${data.rawRequest.country} · ${data.rawRequest.businessUnit} · created ${formatDateTime(data.rawRequest.createdAt)} · required by ${formatDate(data.rawRequest.requiredByDate)} · Evaluation from ${formatDateDdMmYyyy(selectedRun.startedAt)}`
                : `${data.rawRequest.country} · ${data.rawRequest.businessUnit} · created ${formatDateTime(data.rawRequest.createdAt)} · required by ${formatDate(data.rawRequest.requiredByDate)}`
            }
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {showReturnToLatest ? (
            <Link
              href={`/cases/${data.id}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1.5")}
            >
              <ArrowLeft className="size-3.5" />
              Return to latest decision
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
          <Button size="sm">
            <TimerReset className="size-3.5" />
            Escalate
          </Button>
        </div>
      </div>

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
              label="Country Scope"
              value={data.rawRequest.deliveryCountries.join(", ")}
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
                    label="Request language"
                    value={data.rawRequest.requestLanguage}
                  />
                  <FieldCell
                    label="Business unit"
                    value={data.rawRequest.businessUnit}
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
                value={effectiveEvaluatedCount}
                helper="Shortlist plus excluded rows"
              />
              <MiniMetric
                label="Compliant suppliers"
                value={effectiveShortlist.length}
                helper="Suppliers still eligible after policy filters"
              />
              <MiniMetric
                label="Lowest compliant price"
                value={formatCurrency(effectiveLowestPrice, data.recommendation.currency)}
                helper="Best commercial baseline"
              />
              <MiniMetric
                label="Fastest expedited lead time"
                value={
                  effectiveFastestExpedited === null
                    ? "Not available"
                    : `${effectiveFastestExpedited} days`
                }
                helper="Closest feasible delivery option"
              />
            </section>

            <section className="min-w-0 space-y-4">
              <Card className="h-fit w-full max-w-full overflow-hidden">
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
                          <TableHead>Rules</TableHead>
                          <TableHead>Policy</TableHead>
                          <TableHead>Quality</TableHead>
                          <TableHead>Risk</TableHead>
                          <TableHead>ESG</TableHead>
                          <TableHead>Flags</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {visibleSuppliers.map(({ supplier, breakdown }) => {
                          const { hardPassed, hardTotal, policyPassed, policyTotal } =
                            getRuleCounts(breakdown)
                          const rulesLabel =
                            data.evaluationRuns.length > 0
                              ? `${hardPassed}/${hardTotal}`
                              : "—"
                          const policyLabel =
                            data.evaluationRuns.length > 0
                              ? `${policyPassed}/${policyTotal}`
                              : "—"
                          return (
                            <TableRow
                              key={supplier.supplierId}
                              className={cn(
                                supplier.rank === 1 ? "bg-emerald-50/40" : "",
                                "cursor-pointer transition-colors hover:bg-muted/50",
                              )}
                              onClick={() =>
                                setSelectedSupplierDetail({
                                  supplier,
                                  breakdown,
                                })
                              }
                              tabIndex={0}
                              role="button"
                              aria-label={`View details for ${supplier.supplierName}`}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault()
                                  setSelectedSupplierDetail({
                                    supplier,
                                    breakdown,
                                  })
                                }
                              }}
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
                                <div className="space-y-0.5">
                                  <p className="font-medium">
                                    {supplier.supplierName}
                                  </p>
                                  <p className="text-xs uppercase tracking-wider text-muted-foreground">
                                    {supplier.supplierId}
                                  </p>
                                </div>
                              </TableCell>
                              <TableCell className="text-sm">
                                {supplier.pricingTierApplied}
                              </TableCell>
                              <TableCell className="font-medium tabular-nums">
                                <div>
                                  {formatCurrency(
                                    supplier.totalPrice,
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
                              </TableCell>
                              <TableCell className="tabular-nums">
                                <div>{supplier.standardLeadTimeDays}d std</div>
                                <div className="text-xs text-muted-foreground">
                                  {supplier.expeditedLeadTimeDays}d exp
                                </div>
                              </TableCell>
                              <TableCell className="tabular-nums text-sm">
                                {rulesLabel}
                              </TableCell>
                              <TableCell className="tabular-nums text-sm">
                                {policyLabel}
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
                              <TableCell className="align-top py-2">
                                <div className="flex max-w-[100px] flex-col items-start gap-0.5">
                                  {[
                                    supplier.preferred && (
                                      <StatusBadge
                                        key="preferred"
                                        label="Preferred"
                                        tone="info"
                                        className="shrink-0"
                                      />
                                    ),
                                    supplier.incumbent && (
                                      <StatusBadge
                                        key="incumbent"
                                        label="Incumbent"
                                        tone="neutral"
                                        className="shrink-0"
                                      />
                                    ),
                                    supplier.policyCompliant ? (
                                      <StatusBadge
                                        key="compliant"
                                        label="Compliant"
                                        tone="success"
                                        className="shrink-0"
                                      />
                                    ) : (
                                      <StatusBadge
                                        key="conflict"
                                        label="Conflict"
                                        tone="destructive"
                                        className="shrink-0"
                                      />
                                    ),
                                  ]
                                    .filter(Boolean)
                                    .slice(0, 2)}
                                </div>
                              </TableCell>
                            </TableRow>
                          )
                        })}
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
                    {effectiveExcluded.map((supplier) => (
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
          <div className="space-y-5">
            <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
            <Card>
              <CardHeader>
                <CardTitle>Decision timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {data.auditTrail.timeline.map((event, index) => {
                  const isRunEvent = event.kind === "evaluation_run" && event.runId
                  const content = (
                    <>
                      {index !== data.auditTrail.timeline.length - 1 ? (
                        <div className="absolute left-[9px] top-6 h-[calc(100%+0.45rem)] w-px bg-border" />
                      ) : null}
                      <div className="absolute left-0 top-1 size-5 rounded-full border bg-card" />
                      <p className="text-xs font-medium text-muted-foreground">
                        {formatDateTime(event.timestamp)}
                      </p>
                      <h3 className="mt-1 text-sm font-semibold">
                        {event.title}
                      </h3>
                      <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                        {event.description}
                      </p>
                    </>
                  )
                  return (
                    <div key={event.id} className="relative pl-7">
                      {isRunEvent ? (
                        <Link
                          href={`/cases/eval/${event.runId}`}
                          className="block rounded-lg border border-transparent p-4 transition-colors hover:border-primary/30 hover:bg-muted/50"
                        >
                          {content}
                        </Link>
                      ) : (
                        content
                      )}
                    </div>
                  )
                })}
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
          </div>
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

  const effectiveBreakdown =
    breakdown ?? (isLoading ? null : fetchedBreakdown)

  useEffect(() => {
    if (breakdown || !requestId || !supplier.supplierId) {
      return
    }
    let cancelled = false
    // Avoid synchronous state updates inside the effect callback.
    // We kick off loading indicators on the next microtask.
    Promise.resolve().then(() => {
      if (cancelled) return
      setIsLoading(true)
      setFetchError(null)
    })
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
            result: ((c.skipped ? "skipped" : c.result) ?? "skipped") as RuleCheckResult,
            checkedAt: c.checked_at,
          })),
          policyChecks: p.map((c: { check_id: string; rule_id: string; version_id: string; supplier_id: string | null; result: string; checked_at: string }) => ({
            checkId: c.check_id,
            ruleId: c.rule_id,
            versionId: c.version_id,
            supplierId: c.supplier_id,
            result: c.result as RuleCheckResult,
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
                        label={check.result}
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
                        label={check.result}
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
        <StatusBadge label={run.status} tone="info" />
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
                              <StatusBadge label={check.result} tone={toneForCheckResult(check.result)} />
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
                              <StatusBadge label={check.result} tone={toneForCheckResult(check.result)} />
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
