"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { AlertTriangle, ArrowRight, BarChart3, Filter } from "lucide-react"

import { formatCurrency, formatDateTime } from "@/lib/data/formatters"
import { MetricCard } from "@/components/shared/metric-card"
import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type {
  CaseListItem,
  CaseStatus,
  DashboardDataState,
  DashboardInsights,
  DashboardMetric,
} from "@/lib/types/case"
import { cn } from "@/lib/utils"

interface OverviewPageProps {
  metrics: DashboardMetric[]
  cases: CaseListItem[]
  dataState: DashboardDataState
  insights: DashboardInsights
}

const statusLabelMap: Record<CaseStatus, string> = {
  received: "Received",
  parsed: "Parsed",
  pending_review: "Pending review",
  evaluated: "Evaluated",
  recommended: "Recommended",
  escalated: "Escalated",
  resolved: "Resolved",
}

function getStatusTone(status: CaseStatus) {
  if (status === "resolved" || status === "recommended") return "success"
  if (status === "pending_review" || status === "escalated") return "warning"
  return "neutral"
}

export function OverviewPage({
  metrics,
  cases,
  dataState,
  insights,
}: OverviewPageProps) {
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")
  const [countryFilter, setCountryFilter] = useState<string>("all")
  const [attentionOnly, setAttentionOnly] = useState(false)

  const filteredCases = useMemo(() => {
    return cases.filter((entry) => {
      const matchesStatus =
        statusFilter === "all" ? true : entry.status === statusFilter
      const matchesCategory =
        categoryFilter === "all" ? true : entry.category === categoryFilter
      const matchesCountry =
        countryFilter === "all" ? true : entry.countryLabel === countryFilter
      const matchesAttention = attentionOnly ? entry.needsAttention : true

      return (
        matchesStatus && matchesCategory && matchesCountry && matchesAttention
      )
    })
  }, [attentionOnly, cases, categoryFilter, countryFilter, statusFilter])

  const blockedCases = useMemo(
    () =>
      filteredCases.filter(
        (entry) => entry.recommendationStatus === "cannot_proceed",
      ),
    [filteredCases],
  )
  const escalatedCases = useMemo(
    () => filteredCases.filter((entry) => entry.escalationStatus !== "none"),
    [filteredCases],
  )

  const statusChartRows = useMemo(() => {
    const counts = new Map<CaseStatus, number>()
    for (const entry of filteredCases) {
      counts.set(entry.status, (counts.get(entry.status) ?? 0) + 1)
    }

    return insights.filterOptions.statuses
      .map((status) => ({
        status,
        label: statusLabelMap[status],
        count: counts.get(status) ?? 0,
      }))
      .filter((entry) => entry.count > 0)
      .sort((a, b) => b.count - a.count)
  }, [filteredCases, insights.filterOptions.statuses])

  const resetFilters = () => {
    setStatusFilter("all")
    setCategoryFilter("all")
    setCountryFilter("all")
    setAttentionOnly(false)
  }

  const activeFiltersCount =
    Number(statusFilter !== "all") +
    Number(categoryFilter !== "all") +
    Number(countryFilter !== "all") +
    Number(attentionOnly)

  return (
    <div className="space-y-8">
      <div className="animate-fade-in-up flex flex-col gap-2 @xl/main:flex-row @xl/main:items-end @xl/main:justify-between">
        <SectionHeading
          eyebrow="Overview"
          title="Sourcing overview"
          description="Quick operational snapshot with filters and focused queues for action."
        />
        <div className="text-xs text-muted-foreground">
          <p suppressHydrationWarning>
            Snapshot as of {formatDateTime(dataState.asOf)}
          </p>
          <p className="mt-1">
            Showing {filteredCases.length} of {cases.length} cases
          </p>
        </div>
      </div>

      {dataState.mode === "stale" ? (
        <Card
          className="animate-fade-in-up border-amber-300 bg-amber-50/70 text-amber-900"
          style={{ animationDelay: "40ms" }}
        >
          <CardContent className="flex flex-col gap-1 pt-4">
            <p className="flex items-center gap-2 text-sm font-medium">
              <AlertTriangle className="size-4" />
              Backend temporarily unavailable. Showing last successful snapshot.
            </p>
            <p className="text-xs text-amber-800" suppressHydrationWarning>
              Snapshot as of {formatDateTime(dataState.asOf)}.
              {dataState.reason ? ` ${dataState.reason}` : ""}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <section
        className="animate-fade-in-up grid gap-3 @xl/main:grid-cols-2 @3xl/main:grid-cols-4"
        style={{ animationDelay: "80ms" }}
      >
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.valueLabel ?? metric.value}
            helper={metric.helper}
            tone={metric.tone}
          />
        ))}
      </section>

      <Card
        className="animate-fade-in-up"
        style={{ animationDelay: "120ms" }}
      >
        <CardHeader className="border-b pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="size-4 text-muted-foreground" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="flex flex-col gap-3 @2xl/main:flex-row @2xl/main:items-center">
            <div className="grid flex-1 gap-3 @2xl/main:grid-cols-3">
              <Select
                value={statusFilter}
                onValueChange={(value) => setStatusFilter(value ?? "all")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {insights.filterOptions.statuses.map((status) => (
                    <SelectItem key={status} value={status}>
                      {statusLabelMap[status]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={categoryFilter}
                onValueChange={(value) => setCategoryFilter(value ?? "all")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {insights.filterOptions.categories.map((category) => (
                    <SelectItem key={category} value={category}>
                      {category}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={countryFilter}
                onValueChange={(value) => setCountryFilter(value ?? "all")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Country" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All countries</SelectItem>
                  {insights.filterOptions.countries.map((country) => (
                    <SelectItem key={country} value={country}>
                      {country}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={attentionOnly}
                  onCheckedChange={(checked) => setAttentionOnly(checked === true)}
                />
                Needs attention
              </label>
              <Button
                variant="outline"
                size="sm"
                onClick={resetFilters}
                disabled={activeFiltersCount === 0}
              >
                Reset
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <section
        className="animate-fade-in-up grid gap-6 @3xl/main:grid-cols-2"
        style={{ animationDelay: "160ms" }}
      >
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="size-4 text-muted-foreground" />
              Case status mix
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {statusChartRows.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No cases match the selected filters.
              </p>
            ) : (
              (() => {
                const maxCount = Math.max(
                  ...statusChartRows.map((entry) => entry.count),
                )
                return statusChartRows.map((entry) => (
                  <div key={entry.status} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2">
                        <StatusBadge
                          label={entry.label}
                          tone={getStatusTone(entry.status)}
                        />
                      </div>
                      <span className="font-medium tabular-nums">{entry.count}</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-primary/70 transition-all"
                        style={{
                          width: `${(entry.count / maxCount) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              })()
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Spend by category</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights.spendByCategory.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Spend analytics are currently unavailable.
              </p>
            ) : (
              (() => {
                const maxSpend = Math.max(
                  ...insights.spendByCategory.map((entry) => entry.totalSpend),
                )
                return insights.spendByCategory.map((entry) => (
                  <div key={entry.category} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-xs font-medium">{entry.category}</p>
                      <p className="shrink-0 text-xs text-muted-foreground">
                        {formatCurrency(entry.totalSpend)} · {entry.awardCount} awards
                      </p>
                    </div>
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-emerald-500/80 transition-all"
                        style={{
                          width: `${maxSpend > 0 ? (entry.totalSpend / maxSpend) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              })()
            )}
          </CardContent>
        </Card>
      </section>

      <section
        className="animate-fade-in-up grid gap-6 @3xl/main:grid-cols-2"
        style={{ animationDelay: "220ms" }}
      >
        <Card>
          <CardHeader className="flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Blocked cases</CardTitle>
            <Link
              href="/escalations"
              className={buttonVariants({ variant: "ghost", size: "sm" })}
            >
              View all
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {blockedCases.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No blocked cases for this filter set.
              </p>
            ) : (
              blockedCases.slice(0, 5).map((entry) => (
                <Link
                  key={entry.requestId}
                  href={`/cases/${entry.requestId}`}
                  className="group flex items-center justify-between gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {entry.requestId}
                      </span>
                      <StatusBadge label="cannot proceed" tone="destructive" />
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {entry.title}
                    </p>
                    <p
                      className={cn(
                        "mt-1 truncate text-[11px] text-muted-foreground",
                        entry.needsAttention && "text-amber-700",
                      )}
                      suppressHydrationWarning
                    >
                      {entry.businessUnit} · {entry.countryLabel} · updated{" "}
                      {formatDateTime(entry.lastUpdated)}
                    </p>
                  </div>
                  <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Recent escalations</CardTitle>
            <Link
              href="/inbox"
              className={buttonVariants({ variant: "ghost", size: "sm" })}
            >
              Open inbox
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {escalatedCases.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No escalations for this filter set.
              </p>
            ) : (
              escalatedCases.slice(0, 5).map((entry) => (
                <Link
                  key={entry.requestId}
                  href={`/cases/${entry.requestId}`}
                  className="group flex items-center justify-between gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {entry.requestId}
                      </span>
                      <StatusBadge
                        label={entry.escalationStatus}
                        tone={
                          entry.escalationStatus === "blocking"
                            ? "destructive"
                            : "warning"
                        }
                      />
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {entry.title}
                    </p>
                    <p
                      className="mt-1 truncate text-[11px] text-muted-foreground"
                      suppressHydrationWarning
                    >
                      {(entry.scenarioTags ?? []).slice(0, 3).join(", ") ||
                        "standard"}{" "}
                      · updated {formatDateTime(entry.lastUpdated)}
                    </p>
                  </div>
                  <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
