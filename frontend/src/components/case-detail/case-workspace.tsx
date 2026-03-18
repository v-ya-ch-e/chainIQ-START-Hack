import { Download, Play, ShieldCheck, TimerReset } from "lucide-react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button } from "@/components/ui/button"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  scoreTone,
  severityTone,
} from "@/lib/data/formatters"
import type { CaseDetail } from "@/lib/types/case"

interface CaseWorkspaceProps {
  data: CaseDetail
}

export function CaseWorkspace({ data }: CaseWorkspaceProps) {
  const blockingIssues = data.validationIssues.filter((issue) => issue.blocking)
  const recommendedSupplier = data.recommendation.recommendedSupplier
  const evaluatedSuppliers =
    data.supplierShortlist.length + data.excludedSuppliers.length

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
          <Button variant="outline" size="sm">
            <Play className="size-3.5" />
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
            />
            <FieldCell
              label="Last Updated"
              value={formatDateTime(data.lastUpdated)}
            />
          </CardContent>
        </Card>
      </section>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="animate-fade-in-up space-y-4" style={{ animationDelay: "160ms" }}>
        <TabsList
          variant="line"
          className="w-full justify-start rounded-none border-b p-0"
        >
          <TabsTrigger value="overview" className="px-4 py-2.5">
            Overview
          </TabsTrigger>
          <TabsTrigger value="suppliers" className="px-4 py-2.5">
            Suppliers
          </TabsTrigger>
          <TabsTrigger value="escalations" className="px-4 py-2.5">
            Escalations
          </TabsTrigger>
          <TabsTrigger value="audit" className="px-4 py-2.5">
            Audit Trace
          </TabsTrigger>
        </TabsList>

        {/* Overview tab */}
        <TabsContent value="overview">
          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Original request</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg border bg-muted/40 p-3">
                  <p className="text-sm leading-relaxed">
                    {data.rawRequest.requestText}
                  </p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
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
              <CardContent className="grid gap-2 sm:grid-cols-2">
                {data.interpretedRequirements.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-lg border bg-muted/30 p-3"
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
                      className={`mt-1 text-sm leading-relaxed ${item.emphasis ? "font-medium" : "text-muted-foreground"}`}
                    >
                      {item.value}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Validation & issues</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {data.validationIssues.map((issue) => (
                  <div
                    key={issue.issueId}
                    className="rounded-lg border p-3"
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

            <Card>
              <CardHeader>
                <CardTitle>Policy evaluation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {data.policyCards.map((policy) => (
                  <div
                    key={policy.ruleId}
                    className="rounded-lg border p-3"
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
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
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
        <TabsContent value="suppliers">
          <div className="space-y-4">
            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
                value={formatCurrency(
                  Math.min(
                    ...data.supplierShortlist.map((entry) => entry.totalPrice),
                  ),
                  data.recommendation.currency,
                )}
                helper="Best commercial baseline"
              />
              <MiniMetric
                label="Fastest expedited lead time"
                value={`${Math.min(...data.supplierShortlist.map((entry) => entry.expeditedLeadTimeDays))} days`}
                helper="Closest feasible delivery option"
              />
            </section>

            <Card>
              <CardHeader>
                <CardTitle>Supplier comparison</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="overflow-hidden rounded-lg border">
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
                              <p className="max-w-[260px] text-xs leading-relaxed text-muted-foreground">
                                {supplier.recommendationNote}
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
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                <Separator />

                <div className="space-y-3">
                  <h3 className="text-sm font-semibold">Excluded suppliers</h3>
                  {data.excludedSuppliers.map((supplier) => (
                    <div
                      key={supplier.supplierId}
                      className="rounded-lg border p-3"
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
                </div>

                {data.historicalPrecedent ? (
                  <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4">
                    <h3 className="text-sm font-semibold">
                      {data.historicalPrecedent.title}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      {data.historicalPrecedent.description}
                    </p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      {data.historicalPrecedent.metrics.map((metric) => (
                        <FieldCell
                          key={metric.label}
                          label={metric.label}
                          value={metric.value}
                        />
                      ))}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Escalations tab */}
        <TabsContent value="escalations">
          <div className="space-y-4">
            {data.escalations.some((entry) => entry.blocking) ? (
              <Card className="border-rose-200 bg-rose-50/50">
                <CardContent className="px-4 py-4">
                  <p className="text-xs font-medium uppercase tracking-wider text-rose-700">
                    Blocking escalation state
                  </p>
                  <h3 className="mt-1 text-base font-semibold text-rose-900">
                    Autonomous progression is paused
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-rose-800/70">
                    One or more escalation objects require human review before
                    the sourcing case can proceed to award.
                  </p>
                </CardContent>
              </Card>
            ) : null}

            <div className="grid gap-3">
              {data.escalations.map((entry) => (
                <Card key={entry.escalationId}>
                  <CardContent className="px-4 py-4">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <StatusBadge
                            label={entry.escalationId}
                            tone="neutral"
                          />
                          <StatusBadge label={entry.rule} tone="info" />
                          <StatusBadge
                            label={entry.status}
                            tone={
                              entry.status === "resolved"
                                ? "success"
                                : entry.status === "acknowledged"
                                  ? "warning"
                                  : "destructive"
                            }
                          />
                          {entry.blocking ? (
                            <StatusBadge label="blocking" tone="destructive" />
                          ) : (
                            <StatusBadge label="advisory" tone="warning" />
                          )}
                        </div>
                        <h3 className="text-sm font-semibold">
                          Escalate to {entry.escalateTo}
                        </h3>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                          {entry.trigger}
                        </p>
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2 xl:min-w-[280px]">
                        <FieldCell label="Target" value={entry.escalateTo} />
                        <FieldCell
                          label="Next action"
                          value={entry.nextAction}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </TabsContent>

        {/* Audit tab */}
        <TabsContent value="audit">
          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Decision timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.auditTrail.timeline.map((event, index) => (
                  <div key={event.id} className="relative pl-7">
                    {index !== data.auditTrail.timeline.length - 1 ? (
                      <div className="absolute left-[9px] top-6 h-[calc(100%+0.25rem)] w-px bg-border" />
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
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Audit facts</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-2 sm:grid-cols-2">
                  <FieldCell
                    label="Policies checked"
                    value={data.auditTrail.policiesChecked.join(", ")}
                  />
                  <FieldCell
                    label="Suppliers evaluated"
                    value={data.auditTrail.supplierIdsEvaluated.join(", ")}
                  />
                  <FieldCell
                    label="Pricing tiers applied"
                    value={data.auditTrail.pricingTiersApplied}
                  />
                  <FieldCell
                    label="Data sources used"
                    value={data.auditTrail.dataSourcesUsed.join(", ")}
                  />
                  <FieldCell
                    label="Historical awards consulted"
                    value={
                      data.auditTrail.historicalAwardsConsulted ? "Yes" : "No"
                    }
                  />
                  <FieldCell
                    label="Historical award note"
                    value={data.auditTrail.historicalAwardNote}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Reasoning trace</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {data.auditTrail.reasoningTrace.map((step, index) => (
                    <div key={step} className="rounded-lg border p-3">
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
        </TabsContent>
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
    <div className="rounded-lg border bg-card/50 p-3">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-base font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{helper}</p>
    </div>
  )
}

function FieldCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm leading-relaxed">{value}</p>
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
    <Card>
      <CardContent className="space-y-1 px-4 py-3">
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
