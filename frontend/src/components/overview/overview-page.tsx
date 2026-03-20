"use client"

import Link from "next/link"
import {
  memo,
  useCallback,
  useLayoutEffect,
  useMemo,
  useState,
} from "react"
import { AlertTriangle, ArrowRight } from "lucide-react"

import {
  TopbarFilters,
  topbarFilterControlClassName,
} from "@/components/app-shell/topbar-filters"
import { useSetWorkspaceHeaderActions } from "@/components/app-shell/workspace-header-actions"
import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import {
  displayCaseStatus,
  formatCountryDisplayName,
  formatDateTime,
} from "@/lib/data/formatters"
import {
  buildFilterOptions,
  labelForFilterValue,
  type FilterOption,
} from "@/lib/filter-options"
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

const OVERVIEW_WIDGET_LIMIT = 4

function getStatusTone(status: CaseStatus) {
  if (status === "resolved" || status === "recommended") return "success"
  if (status === "pending_review" || status === "escalated") return "warning"
  return "neutral"
}

function sortByLastUpdatedDesc(entries: CaseListItem[]) {
  return [...entries].sort((a, b) => {
    return new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime()
  })
}

const OverviewWorkspaceToolbar = memo(function OverviewWorkspaceToolbar({
  statusFilter,
  categoryFilter,
  countryFilter,
  attentionOnly,
  statusOptions,
  categoryOptions,
  countryOptions,
  onStatusChange,
  onCategoryChange,
  onCountryChange,
  onAttentionChange,
  onReset,
  canReset,
}: {
  statusFilter: string
  categoryFilter: string
  countryFilter: string
  attentionOnly: boolean
  statusOptions: FilterOption[]
  categoryOptions: FilterOption[]
  countryOptions: FilterOption[]
  onStatusChange: (value: string | null) => void
  onCategoryChange: (value: string | null) => void
  onCountryChange: (value: string | null) => void
  onAttentionChange: (checked: boolean) => void
  onReset: () => void
  canReset: boolean
}) {
  const statusTriggerLabel = labelForFilterValue(
    statusOptions,
    statusFilter,
    "All statuses",
  )
  const categoryTriggerLabel = labelForFilterValue(
    categoryOptions,
    categoryFilter,
    "All categories",
  )
  const countryTriggerLabel = labelForFilterValue(
    countryOptions,
    countryFilter,
    "All countries",
  )

  return (
    <TopbarFilters>
      <Select value={statusFilter} onValueChange={onStatusChange}>
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[10.5rem] grow border-input/80 transition-colors duration-150 sm:max-w-[12rem] sm:grow-0",
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
      <Select value={categoryFilter} onValueChange={onCategoryChange}>
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[11rem] grow border-input/80 transition-colors duration-150 sm:max-w-[13rem] sm:grow-0",
            topbarFilterControlClassName,
          )}
        >
          <span className="truncate text-left" data-slot="select-value">
            {categoryTriggerLabel}
          </span>
        </SelectTrigger>
        <SelectContent>
          {categoryOptions.map((category) => (
            <SelectItem
              key={category.value || "__uncategorized"}
              value={category.value}
            >
              {category.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={countryFilter} onValueChange={onCountryChange}>
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[10.5rem] grow border-input/80 transition-colors duration-150 sm:max-w-[12rem] sm:grow-0",
            topbarFilterControlClassName,
          )}
        >
          <span className="truncate text-left" data-slot="select-value">
            {countryTriggerLabel}
          </span>
        </SelectTrigger>
        <SelectContent>
          {countryOptions.map((country) => (
            <SelectItem key={country.value} value={country.value}>
              {country.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <label
        className={cn(
          "flex h-8 shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap border border-input/80 bg-background px-2.5 text-xs text-muted-foreground transition-colors hover:text-foreground",
          topbarFilterControlClassName,
        )}
      >
        <Checkbox
          checked={attentionOnly}
          onCheckedChange={(checked) => onAttentionChange(checked === true)}
        />
        Needs attention
      </label>
      <Button
        variant="outline"
        size="sm"
        className={cn("h-8 shrink-0", topbarFilterControlClassName)}
        onClick={onReset}
        disabled={!canReset}
      >
        Reset
      </Button>
    </TopbarFilters>
  )
})

function InlineStat({
  label,
  value,
  tone = "default",
}: {
  label: string
  value: string
  tone?: "default" | "warning" | "destructive"
}) {
  return (
    <div className="rounded-[var(--overview-strip-inner-radius)] border px-3 py-2 shadow-none">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "mt-1 text-sm font-semibold tabular-nums",
          tone === "warning" && "text-amber-700",
          tone === "destructive" && "text-rose-700",
        )}
      >
        {value}
      </p>
    </div>
  )
}

function CaseActionRow({
  entry,
  detail,
}: {
  entry: CaseListItem
  detail?: string
}) {
  const escalationTone =
    entry.escalationStatus === "blocking" ? "destructive" : "warning"
  const metadata = [
    entry.category || "Uncategorized",
    formatCountryDisplayName(entry.countryLabel),
    entry.businessUnit,
  ]
    .filter(Boolean)
    .join(" · ")

  return (
    <Link
      href={`/cases/${entry.requestId}`}
      className="group flex items-center gap-3 border-t px-3 py-2.5 transition-colors hover:bg-muted/35"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <p className="truncate text-sm font-medium">{entry.title}</p>
          <StatusBadge
            label={displayCaseStatus(entry.status)}
            tone={getStatusTone(entry.status)}
          />
          {entry.escalationStatus !== "none" ? (
            <StatusBadge label={entry.escalationStatus} tone={escalationTone} />
          ) : null}
        </div>
        <p className="mt-1 truncate text-xs text-muted-foreground">{metadata}</p>
        <p
          className="mt-1 truncate text-[11px] text-muted-foreground"
          suppressHydrationWarning
        >
          {detail ?? `Updated ${formatDateTime(entry.lastUpdated)}`}
        </p>
      </div>
      <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </Link>
  )
}

function ActionPanel({
  title,
  actionLabel,
  actionHref,
  items,
  emptyMessage,
  rowDetail,
}: {
  title: string
  actionLabel: string
  actionHref: string
  items: CaseListItem[]
  emptyMessage: string
  rowDetail?: (entry: CaseListItem) => string
}) {
  return (
    <section className="rounded-[var(--layout-inner-radius)] border bg-background shadow-none">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        <Link
          href={actionHref}
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "h-8 px-2.5 text-xs",
          )}
        >
          {actionLabel}
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="px-4 py-4 text-sm text-muted-foreground">{emptyMessage}</p>
      ) : (
        <div>
          {items.map((entry) => (
            <CaseActionRow
              key={entry.requestId}
              entry={entry}
              detail={rowDetail?.(entry)}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export function OverviewPage(props: OverviewPageProps) {
  const { cases, dataState, insights } = props
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")
  const [countryFilter, setCountryFilter] = useState<string>("all")
  const [attentionOnly, setAttentionOnly] = useState(false)

  const statusOptions = useMemo(
    () => [
      { value: "all", label: "All statuses" },
      ...buildFilterOptions(insights.filterOptions.statuses, (status) =>
        displayCaseStatus(status),
      ),
    ],
    [insights.filterOptions.statuses],
  )

  const categoryOptions = useMemo(
    () => [
      { value: "all", label: "All categories" },
      ...buildFilterOptions(insights.filterOptions.categories, (category) =>
        category.trim() ? category : "Uncategorized",
      ),
    ],
    [insights.filterOptions.categories],
  )

  const countryOptions = useMemo(
    () => [
      { value: "all", label: "All countries" },
      ...buildFilterOptions(insights.filterOptions.countries, (country) =>
        formatCountryDisplayName(country),
      ),
    ],
    [insights.filterOptions.countries],
  )

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

  const needsAttentionCases = useMemo(
    () => sortByLastUpdatedDesc(filteredCases.filter((entry) => entry.needsAttention)),
    [filteredCases],
  )

  const recentEscalationCases = useMemo(
    () =>
      sortByLastUpdatedDesc(
        filteredCases.filter((entry) => entry.escalationStatus !== "none"),
      ),
    [filteredCases],
  )

  const dueSoonCases = useMemo(() => {
    return [...filteredCases]
      .filter((entry) => !Number.isNaN(new Date(entry.requiredByDate).getTime()))
      .filter((entry) => entry.status !== "resolved")
      .sort((a, b) => {
        const dueDiff =
          new Date(a.requiredByDate).getTime() -
          new Date(b.requiredByDate).getTime()
        if (dueDiff !== 0) return dueDiff
        return (
          new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime()
        )
      })
  }, [filteredCases])

  const readyOutcomeCases = useMemo(
    () =>
      sortByLastUpdatedDesc(
        filteredCases.filter(
          (entry) =>
            entry.status === "recommended" ||
            entry.status === "resolved" ||
            entry.recommendationStatus === "proceed",
        ),
      ),
    [filteredCases],
  )

  const blockingCount = useMemo(
    () =>
      filteredCases.filter(
        (entry) => entry.recommendationStatus === "cannot_proceed",
      ).length,
    [filteredCases],
  )

  const activeFiltersCount =
    Number(statusFilter !== "all") +
    Number(categoryFilter !== "all") +
    Number(countryFilter !== "all") +
    Number(attentionOnly)

  const setHeaderActions = useSetWorkspaceHeaderActions()

  const resetFilters = useCallback(() => {
    setStatusFilter("all")
    setCategoryFilter("all")
    setCountryFilter("all")
    setAttentionOnly(false)
  }, [])

  const handleStatusFilterChange = useCallback((value: string | null) => {
    setStatusFilter(value ?? "all")
  }, [])

  const handleCategoryFilterChange = useCallback((value: string | null) => {
    setCategoryFilter(value ?? "all")
  }, [])

  const handleCountryFilterChange = useCallback((value: string | null) => {
    setCountryFilter(value ?? "all")
  }, [])

  useLayoutEffect(
    () => {
      setHeaderActions(
        <OverviewWorkspaceToolbar
          statusFilter={statusFilter}
          categoryFilter={categoryFilter}
          countryFilter={countryFilter}
          attentionOnly={attentionOnly}
          statusOptions={statusOptions}
          categoryOptions={categoryOptions}
          countryOptions={countryOptions}
          onStatusChange={handleStatusFilterChange}
          onCategoryChange={handleCategoryFilterChange}
          onCountryChange={handleCountryFilterChange}
          onAttentionChange={setAttentionOnly}
          onReset={resetFilters}
          canReset={activeFiltersCount > 0}
        />,
      )
      return () => setHeaderActions(null)
    },
    [
      setHeaderActions,
      statusFilter,
      categoryFilter,
      countryFilter,
      attentionOnly,
      activeFiltersCount,
      statusOptions,
      categoryOptions,
      countryOptions,
      handleStatusFilterChange,
      handleCategoryFilterChange,
      handleCountryFilterChange,
      resetFilters,
    ],
  )

  return (
    <div className="space-y-4">
      <div className="animate-fade-in-up flex flex-col gap-1.5 @xl/main:flex-row @xl/main:items-end @xl/main:justify-between">
        <SectionHeading
          eyebrow="Overview"
          title="Sourcing overview"
          description="Operational triage for requests requiring action."
        />
        <p className="text-xs text-muted-foreground" suppressHydrationWarning>
          Snapshot as of {formatDateTime(dataState.asOf)}
        </p>
      </div>

      {dataState.mode === "stale" ? (
        <div
          className="animate-fade-in-up flex items-start gap-2 rounded-[var(--layout-inner-radius)] border border-amber-300/80 bg-amber-50/60 px-3 py-2 text-xs text-amber-900 shadow-none"
          style={{ animationDelay: "30ms" }}
        >
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          <p suppressHydrationWarning>
            Backend temporarily unavailable. Showing last successful snapshot from{" "}
            {formatDateTime(dataState.asOf)}.
            {dataState.reason ? ` ${dataState.reason}` : ""}
          </p>
        </div>
      ) : null}

      <section
        className="animate-fade-in-up [--overview-strip-inner-padding:0.375rem] [--overview-strip-inner-radius:var(--radius-md)] [--overview-strip-outer-radius:calc(var(--overview-strip-inner-radius)+var(--overview-strip-inner-padding))] rounded-[var(--overview-strip-outer-radius)] border p-[var(--overview-strip-inner-padding)] shadow-none"
        style={{ animationDelay: "60ms" }}
      >
        <div className="grid gap-2 sm:grid-cols-2 @3xl/main:grid-cols-4">
          <InlineStat
            label="Visible cases"
            value={`${filteredCases.length} / ${cases.length}`}
          />
          <InlineStat
            label="Needs attention"
            value={String(needsAttentionCases.length)}
            tone="warning"
          />
          <InlineStat
            label="Blocking"
            value={String(blockingCount)}
            tone="destructive"
          />
          <InlineStat
            label="Open escalations"
            value={String(recentEscalationCases.length)}
            tone="warning"
          />
        </div>
      </section>

      <section
        className="animate-fade-in-up grid gap-4 @3xl/main:grid-cols-2 @5xl/main:grid-cols-4"
        style={{ animationDelay: "90ms" }}
      >
        <ActionPanel
          title="Needs attention"
          actionLabel="Open inbox"
          actionHref="/inbox"
          items={needsAttentionCases.slice(0, OVERVIEW_WIDGET_LIMIT)}
          emptyMessage="No cases currently require attention for this filter set."
        />
        <ActionPanel
          title="Recent escalations"
          actionLabel="View escalations"
          actionHref="/escalations"
          items={recentEscalationCases.slice(0, OVERVIEW_WIDGET_LIMIT)}
          emptyMessage="No escalations for this filter set."
        />
        <ActionPanel
          title="Due soon"
          actionLabel="Open inbox"
          actionHref="/inbox"
          items={dueSoonCases.slice(0, OVERVIEW_WIDGET_LIMIT)}
          emptyMessage="No upcoming due dates in this filter set."
          rowDetail={(entry) => `Due ${formatDateTime(entry.requiredByDate)}`}
        />
        <ActionPanel
          title="Ready outcomes"
          actionLabel="Open pipeline"
          actionHref="/pipeline"
          items={readyOutcomeCases.slice(0, OVERVIEW_WIDGET_LIMIT)}
          emptyMessage="No ready outcomes in this filter set."
          rowDetail={(entry) =>
            entry.supplierLabel
              ? `Preferred supplier ${entry.supplierLabel}`
              : `Updated ${formatDateTime(entry.lastUpdated)}`
          }
        />
      </section>
    </div>
  )
}
