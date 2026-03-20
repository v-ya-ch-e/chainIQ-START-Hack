"use client"

import Link from "next/link"
import {
  memo,
  type CSSProperties,
  useCallback,
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react"
import {
  AlertTriangle,
  Building2,
  Cpu,
  FileText,
  RefreshCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react"

import { AuditEntryDetails } from "@/components/audit/audit-entry-details"
import {
  TopbarFilters,
  topbarFilterControlClassName,
} from "@/components/app-shell/topbar-filters"
import { useSetWorkspaceHeaderActions } from "@/components/app-shell/workspace-header-actions"
import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { formatDateTime } from "@/lib/data/formatters"
import type {
  AuditFeedEvent,
  AuditFeedMeta,
  AuditSummaryMetric,
} from "@/lib/types/case"
import { labelForFilterValue, type FilterOption } from "@/lib/filter-options"
import { cn } from "@/lib/utils"

interface AuditPageProps {
  summary: AuditSummaryMetric[]
  feed: AuditFeedEvent[]
  feedMeta: AuditFeedMeta
}

type AuditTab = "actionable" | "full" | "by-request"
const MAX_RUN_SUGGESTIONS = 8

interface RunSuggestion {
  runId: string
  helper: string
}

const kindLabel: Record<AuditFeedEvent["kind"], string> = {
  source: "Source",
  interpretation: "Interpretation",
  policy: "Policy",
  supplier: "Supplier",
  escalation: "Escalation",
  audit: "Audit",
}

const kindOptions: FilterOption[] = [
  { value: "all", label: "All kinds" },
  { value: "source", label: "Source" },
  { value: "interpretation", label: "Interpretation" },
  { value: "policy", label: "Policy" },
  { value: "supplier", label: "Supplier" },
  { value: "escalation", label: "Escalation" },
  { value: "audit", label: "Audit" },
]

const levelOptions: FilterOption[] = [
  { value: "all", label: "All levels" },
  { value: "info", label: "Info" },
  { value: "warn", label: "Warning" },
  { value: "error", label: "Error" },
]

function getIconForKind(kind: AuditFeedEvent["kind"]) {
  switch (kind) {
    case "source":
      return <FileText className="size-4" />
    case "interpretation":
      return <Cpu className="size-4" />
    case "policy":
      return <ShieldCheck className="size-4" />
    case "supplier":
      return <Building2 className="size-4" />
    case "escalation":
      return <ShieldAlert className="size-4" />
    default:
      return <TerminalSquare className="size-4" />
  }
}

function levelLabel(level?: string) {
  if (!level) return "unknown"
  if (level === "warn") return "warning"
  return level
}

function useDetailSheetMode() {
  const [sheetMode, setSheetMode] = useState(false)

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 1279px)")
    const handleChange = () => {
      setSheetMode(mediaQuery.matches)
    }

    handleChange()
    mediaQuery.addEventListener("change", handleChange)
    return () => mediaQuery.removeEventListener("change", handleChange)
  }, [])

  return sheetMode
}

function AuditEventList({
  events,
  selectedEventId,
  onSelect,
  showCaseId = true,
  emptyMessage,
}: {
  events: AuditFeedEvent[]
  selectedEventId: string | null
  onSelect: (event: AuditFeedEvent) => void
  showCaseId?: boolean
  emptyMessage: string
}) {
  if (events.length === 0) {
    return <p className="py-4 text-sm text-muted-foreground">{emptyMessage}</p>
  }

  return (
    <div className="space-y-2">
      {events.map((event) => {
        const selected = event.id === selectedEventId
        const metaBits = [
          kindLabel[event.kind],
          event.level && event.level !== "info" ? levelLabel(event.level) : null,
          showCaseId ? event.caseTitle || event.caseId : null,
          event.category
            ? `${event.category}${event.stepName ? ` · ${event.stepName}` : ""}`
            : null,
        ].filter(Boolean) as string[]

        return (
          <button
            type="button"
            key={event.id}
            className={cn(
              "group w-full rounded-[var(--layout-inner-radius)] border px-[var(--layout-inner-padding)] py-[calc(var(--layout-inner-padding)*0.9)] text-left transition-colors duration-150 motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
              selected
                ? "border-primary/50 bg-primary/[0.06]"
                : "border-border/80 bg-background hover:border-border hover:bg-muted/20",
            )}
            onClick={() => onSelect(event)}
            aria-pressed={selected}
          >
            <div className="flex items-start gap-2.5">
              <span
                className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-[calc(var(--layout-inner-radius)-0.2rem)] border bg-muted/25 text-muted-foreground"
              >
                {getIconForKind(event.kind)}
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {event.title}
                  </p>
                  <time className="shrink-0 whitespace-nowrap text-xs tabular-nums text-muted-foreground" suppressHydrationWarning>
                    {formatDateTime(event.timestamp)}
                  </time>
                </div>

                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                  {event.description}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                  {metaBits.map((bit, index) => (
                    <span key={`${event.id}-meta-${index}`}>
                      {index > 0 ? "• " : ""}
                      {bit}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}

const AuditWorkspaceToolbar = memo(function AuditWorkspaceToolbar({
  query,
  kindFilter,
  levelFilter,
  runSearch,
  runSuggestions,
  onQueryChange,
  onKindChange,
  onLevelChange,
  onRunSearchChange,
  onReset,
  canReset,
}: {
  query: string
  kindFilter: string
  levelFilter: string
  runSearch: string
  runSuggestions: RunSuggestion[]
  onQueryChange: (value: string) => void
  onKindChange: (value: string | null) => void
  onLevelChange: (value: string | null) => void
  onRunSearchChange: (value: string) => void
  onReset: () => void
  canReset: boolean
}) {
  const kindTriggerLabel = labelForFilterValue(
    kindOptions,
    kindFilter,
    "All kinds",
  )
  const levelTriggerLabel = labelForFilterValue(
    levelOptions,
    levelFilter,
    "All levels",
  )

  return (
    <TopbarFilters>
      <div className="relative h-8 min-w-[14rem] grow basis-full sm:basis-auto sm:max-w-[24rem] sm:grow">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search request, case title, or event text…"
          className={cn(
            "h-8 border-input/80 pl-8 text-sm transition-colors focus-visible:border-ring",
            topbarFilterControlClassName,
          )}
        />
      </div>

      <Select value={kindFilter} onValueChange={onKindChange}>
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[10.5rem] grow transition-[color,box-shadow,opacity] duration-150 sm:max-w-[12rem] sm:grow-0",
            topbarFilterControlClassName,
          )}
        >
          <span className="truncate text-left" data-slot="select-value">
            {kindTriggerLabel}
          </span>
        </SelectTrigger>
        <SelectContent>
          {kindOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={levelFilter} onValueChange={onLevelChange}>
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[10.5rem] grow transition-[color,box-shadow,opacity] duration-150 sm:max-w-[12rem] sm:grow-0",
            topbarFilterControlClassName,
          )}
        >
          <span className="truncate text-left" data-slot="select-value">
            {levelTriggerLabel}
          </span>
        </SelectTrigger>
        <SelectContent>
          {levelOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="relative h-8 min-w-[12rem] grow sm:max-w-[16rem] sm:grow-0">
        <Input
          value={runSearch}
          onChange={(event) => onRunSearchChange(event.target.value)}
          list="audit-run-suggestions"
          placeholder="Search run id..."
          className={cn(
            "h-8 border-input/80 text-sm transition-colors focus-visible:border-ring",
            topbarFilterControlClassName,
          )}
        />
        <datalist id="audit-run-suggestions">
          {runSuggestions.map((suggestion) => (
            <option key={suggestion.runId} value={suggestion.runId}>
              {suggestion.helper}
            </option>
          ))}
        </datalist>
      </div>

      <Button
        variant="outline"
        size="sm"
        onClick={onReset}
        disabled={!canReset}
        className={cn("h-8 shrink-0", topbarFilterControlClassName)}
      >
        <RefreshCcw className="mr-1.5 size-3.5" />
        Reset
      </Button>
    </TopbarFilters>
  )
})

export function AuditPage({ summary, feed, feedMeta }: AuditPageProps) {
  const [query, setQuery] = useState("")
  const [kindFilter, setKindFilter] = useState("all")
  const [levelFilter, setLevelFilter] = useState("all")
  const [runFilter, setRunFilter] = useState("all")
  const [runSearch, setRunSearch] = useState("")
  const [activeTab, setActiveTab] = useState<AuditTab>("actionable")
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [expandedCaseIds, setExpandedCaseIds] = useState<string[]>([])
  const [detailSheetOpen, setDetailSheetOpen] = useState(false)
  const setHeaderActions = useSetWorkspaceHeaderActions()
  const useDetailSheet = useDetailSheetMode()

  const availableRuns = useMemo(() => {
    const runMap = new Map<
      string,
      { runId: string; latestTimestamp: string; caseIds: Set<string> }
    >()

    for (const event of feed) {
      if (!event.runId) continue
      const existing = runMap.get(event.runId)
      if (existing) {
        existing.caseIds.add(event.caseId)
        if (event.timestamp > existing.latestTimestamp) {
          existing.latestTimestamp = event.timestamp
        }
      } else {
        runMap.set(event.runId, {
          runId: event.runId,
          latestTimestamp: event.timestamp,
          caseIds: new Set([event.caseId]),
        })
      }
    }

    return Array.from(runMap.values()).sort((a, b) =>
      b.latestTimestamp.localeCompare(a.latestTimestamp),
    )
  }, [feed])

  const filteredFeed = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()

    return feed.filter((event) => {
      const matchesSearch =
        !normalizedQuery ||
        event.title.toLowerCase().includes(normalizedQuery) ||
        event.description.toLowerCase().includes(normalizedQuery) ||
        event.caseId.toLowerCase().includes(normalizedQuery) ||
        event.caseTitle.toLowerCase().includes(normalizedQuery)

      const matchesKind = kindFilter === "all" || event.kind === kindFilter
      const matchesLevel = levelFilter === "all" || event.level === levelFilter
      const matchesRun = runFilter === "all" || event.runId === runFilter

      return matchesSearch && matchesKind && matchesLevel && matchesRun
    })
  }, [feed, kindFilter, levelFilter, runFilter, query])

  const actionableEvents = useMemo(
    () =>
      filteredFeed.filter(
        (event) =>
          event.level === "error" ||
          event.level === "warn" ||
          event.kind === "escalation",
      ),
    [filteredFeed],
  )

  const eventsByCase = useMemo(() => {
    const groups = new Map<
      string,
      { caseId: string; caseTitle: string; events: AuditFeedEvent[] }
    >()

    for (const event of filteredFeed) {
      const existing = groups.get(event.caseId)
      if (existing) {
        existing.events.push(event)
        continue
      }

      groups.set(event.caseId, {
        caseId: event.caseId,
        caseTitle: event.caseTitle,
        events: [event],
      })
    }

    return Array.from(groups.values())
      .map((group) => {
        const sorted = group.events.sort(
          (a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
        )
        if (runFilter !== "all") return { ...group, events: sorted }

        const latestRunId = sorted.find((event) => event.runId)?.runId
        const deduped = latestRunId
          ? sorted.filter((event) => !event.runId || event.runId === latestRunId)
          : sorted

        return { ...group, events: deduped }
      })
      .sort((a, b) => {
        const aLatest = a.events[0]?.timestamp ?? ""
        const bLatest = b.events[0]?.timestamp ?? ""
        return new Date(bLatest).getTime() - new Date(aLatest).getTime()
      })
  }, [filteredFeed, runFilter])

  const groupedEvents = useMemo(
    () => eventsByCase.flatMap((group) => group.events),
    [eventsByCase],
  )

  const tabEvents = useMemo(() => {
    if (activeTab === "actionable") return actionableEvents
    if (activeTab === "full") return filteredFeed
    return groupedEvents
  }, [activeTab, actionableEvents, filteredFeed, groupedEvents])

  const selectedEvent = useMemo(() => {
    if (tabEvents.length === 0) return null
    if (!selectedEventId) return tabEvents[0]
    return tabEvents.find((event) => event.id === selectedEventId) ?? tabEvents[0]
  }, [selectedEventId, tabEvents])

  const expandedCaseValue = useMemo(() => {
    if (activeTab !== "by-request" || !selectedEvent) return expandedCaseIds
    return expandedCaseIds.includes(selectedEvent.caseId)
      ? expandedCaseIds
      : [selectedEvent.caseId, ...expandedCaseIds]
  }, [activeTab, expandedCaseIds, selectedEvent])

  const deferredSelectedEventId = useDeferredValue(selectedEvent?.id ?? null)
  const detailLoading = Boolean(
    selectedEvent?.id && deferredSelectedEventId !== selectedEvent.id,
  )

  const activeFiltersCount =
    Number(kindFilter !== "all") +
    Number(levelFilter !== "all") +
    Number(runFilter !== "all") +
    Number(query.trim().length > 0)
  const hasActiveFilters = activeFiltersCount > 0

  const resetFilters = useCallback(() => {
    setQuery("")
    setKindFilter("all")
    setLevelFilter("all")
    setRunFilter("all")
    setRunSearch("")
  }, [])

  const handleKindFilterChange = useCallback((value: string | null) => {
    setKindFilter(value ?? "all")
  }, [])

  const handleLevelFilterChange = useCallback((value: string | null) => {
    setLevelFilter(value ?? "all")
  }, [])

  const runSuggestions = useMemo<RunSuggestion[]>(() => {
    const normalizedQuery = runSearch.trim().toLowerCase()
    const ranked = availableRuns
      .map((run) => {
        const caseList = Array.from(run.caseIds).join(", ")
        const runIdLower = run.runId.toLowerCase()
        const casesLower = caseList.toLowerCase()
        const matches =
          !normalizedQuery ||
          runIdLower.includes(normalizedQuery) ||
          casesLower.includes(normalizedQuery)
        if (!matches) return null

        const rank = runIdLower.startsWith(normalizedQuery)
          ? 0
          : runIdLower.includes(normalizedQuery)
            ? 1
            : 2

        return {
          runId: run.runId,
          helper: `${caseList} · ${formatDateTime(run.latestTimestamp)}`,
          rank,
          latestTimestamp: run.latestTimestamp,
        }
      })
      .filter((entry) => entry !== null)
      .sort((a, b) => {
        if (a.rank !== b.rank) return a.rank - b.rank
        return b.latestTimestamp.localeCompare(a.latestTimestamp)
      })
      .slice(0, MAX_RUN_SUGGESTIONS)

    return ranked.map((entry) => ({
      runId: entry.runId,
      helper: entry.helper,
    }))
  }, [availableRuns, runSearch])

  const handleRunSearchChange = useCallback(
    (value: string) => {
      setRunSearch(value)
      const normalized = value.trim().toLowerCase()
      if (!normalized) {
        setRunFilter("all")
        return
      }

      const exact = availableRuns.find(
        (run) => run.runId.toLowerCase() === normalized,
      )
      setRunFilter(exact ? exact.runId : "all")
    },
    [availableRuns],
  )

  const handleSelectEvent = useCallback(
    (event: AuditFeedEvent) => {
      setSelectedEventId(event.id)
      if (activeTab === "by-request") {
        setExpandedCaseIds((current) =>
          current.includes(event.caseId) ? current : [event.caseId, ...current],
        )
      }
      if (useDetailSheet) {
        setDetailSheetOpen(true)
      }
    },
    [activeTab, useDetailSheet],
  )

  const handleTabChange = useCallback((value: string) => {
    if (value === "actionable" || value === "full" || value === "by-request") {
      setActiveTab(value)
      setDetailSheetOpen(false)
    }
  }, [])

  useLayoutEffect(() => {
    setHeaderActions(
      <AuditWorkspaceToolbar
        query={query}
        kindFilter={kindFilter}
        levelFilter={levelFilter}
        runSearch={runSearch}
        runSuggestions={runSuggestions}
        onQueryChange={setQuery}
        onKindChange={handleKindFilterChange}
        onLevelChange={handleLevelFilterChange}
        onRunSearchChange={handleRunSearchChange}
        onReset={resetFilters}
        canReset={hasActiveFilters}
      />,
    )

    return () => setHeaderActions(null)
  }, [
    handleKindFilterChange,
    handleLevelFilterChange,
    handleRunSearchChange,
    hasActiveFilters,
    kindFilter,
    levelFilter,
    query,
    resetFilters,
    runSearch,
    runFilter,
    runSuggestions,
    setHeaderActions,
  ])

  const layoutVars = {
    "--layout-inner-padding": "0.75rem",
    "--layout-inner-radius": "0.875rem",
    "--layout-outer-radius":
      "calc(var(--layout-inner-radius) + var(--layout-inner-padding))",
  } as CSSProperties

  return (
    <div className="space-y-5" style={layoutVars}>
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Audit"
          title="Audit and compliance overview"
          description="Track operational risk, inspect decision traces, and triage high-priority events quickly."
        />
      </div>

      {feedMeta.mode === "degraded" || feedMeta.isTruncated ? (
        <Card className="animate-fade-in-up rounded-[var(--layout-outer-radius)] border-amber-300 bg-amber-50/70 text-amber-900 ring-0" size="sm">
          <CardContent className="flex flex-col gap-1 pt-1.5 text-sm">
            <p className="flex items-center gap-2 font-medium">
              <AlertTriangle className="size-4" />
              Audit data quality notice
            </p>
            <p className="text-xs text-amber-800" suppressHydrationWarning>
              {feedMeta.mode === "degraded"
                ? feedMeta.warning ?? "Audit feed is currently degraded."
                : "Audit feed is truncated to the current fetch limit."}{" "}
              Snapshot at {formatDateTime(feedMeta.asOf)}.
            </p>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section
          className="animate-fade-in-up grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
          style={{ animationDelay: "70ms" }}
        >
          {summary.map((item) => (
            <Card key={item.label} className="rounded-[var(--layout-outer-radius)] ring-0" size="sm">
              <CardContent className="space-y-1 px-[var(--layout-inner-padding)] py-[calc(var(--layout-inner-padding)*0.9)]">
                <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  {item.label}
                </p>
                <p className="text-xl font-semibold tabular-nums tracking-tight">
                  {item.value}
                </p>
                <p className="text-xs text-muted-foreground">{item.helper}</p>
              </CardContent>
            </Card>
          ))}
        </section>

        <Card
          className="animate-fade-in-up rounded-[var(--layout-outer-radius)] ring-0"
          size="sm"
          style={{ animationDelay: "100ms" }}
        >
          <CardHeader className="border-b px-[var(--layout-inner-padding)] pb-[calc(var(--layout-inner-padding)*0.85)]">
            <CardTitle className="text-sm">Feed scope</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 px-[var(--layout-inner-padding)] py-[calc(var(--layout-inner-padding)*0.9)] text-xs">
            <p className="text-muted-foreground">
              Showing <span className="font-semibold text-foreground">{filteredFeed.length}</span> of{" "}
              <span className="font-semibold text-foreground">{feedMeta.totalKnown}</span> entries
            </p>
            <div className="flex flex-wrap items-center gap-1.5">
              {hasActiveFilters ? (
                <StatusBadge
                  label={`${activeFiltersCount} filter${activeFiltersCount > 1 ? "s" : ""} active`}
                  tone="info"
                />
              ) : null}
              {feedMeta.isTruncated ? (
                <StatusBadge label="truncated feed" tone="warning" />
              ) : null}
              {!hasActiveFilters && !feedMeta.isTruncated ? (
                <StatusBadge label="live scope" tone="neutral" />
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>

      <div
        className="animate-fade-in-up grid gap-3 xl:grid-cols-[minmax(0,1fr)_22rem]"
        style={{ animationDelay: "130ms" }}
      >
        <Card className="rounded-[var(--layout-outer-radius)] ring-0">
          <CardContent className="px-[var(--layout-inner-padding)] py-[var(--layout-inner-padding)]">
              <Tabs
                value={activeTab}
                onValueChange={handleTabChange}
                className="space-y-[var(--layout-inner-padding)]"
              >
              <TabsList
                variant="line"
                className="w-full justify-start rounded-none border-b border-border/70 p-0"
              >
                <TabsTrigger
                  value="actionable"
                  className="px-5 py-3"
                >
                  Actionable ({actionableEvents.length})
                </TabsTrigger>
                <TabsTrigger
                  value="full"
                  className="px-5 py-3"
                >
                  Full log ({filteredFeed.length})
                </TabsTrigger>
                <TabsTrigger
                  value="by-request"
                  className="px-5 py-3"
                >
                  By request ({eventsByCase.length})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="actionable" className="space-y-3">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Actionable priority trace</p>
                  <p className="text-xs text-muted-foreground">
                    Warnings, errors, and escalation events that need operator attention.
                  </p>
                </div>
                <AuditEventList
                  events={actionableEvents}
                  selectedEventId={selectedEventId}
                  onSelect={handleSelectEvent}
                  emptyMessage={
                    hasActiveFilters
                      ? "No actionable events match current filters."
                      : "No actionable events available."
                  }
                />
              </TabsContent>

              <TabsContent value="full" className="space-y-3">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Full audit log</p>
                  <p className="text-xs text-muted-foreground">
                    Complete event sequence across all currently visible requests.
                  </p>
                </div>
                <AuditEventList
                  events={filteredFeed}
                  selectedEventId={selectedEventId}
                  onSelect={handleSelectEvent}
                  emptyMessage={
                    hasActiveFilters
                      ? "No events match current filters."
                      : "No audit entries available right now."
                  }
                />
              </TabsContent>

              <TabsContent value="by-request" className="space-y-3">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Grouped by request</p>
                  <p className="text-xs text-muted-foreground">
                    Inspect each request timeline independently for focused review.
                  </p>
                </div>

                {eventsByCase.length > 0 ? (
                  <Accordion
                    type="multiple"
                    value={expandedCaseValue}
                    onValueChange={setExpandedCaseIds}
                    className="w-full space-y-2"
                  >
                    {eventsByCase.map(({ caseId, caseTitle, events }) => (
                      <AccordionItem
                        key={caseId}
                        value={caseId}
                        className="overflow-hidden rounded-[var(--layout-inner-radius)] border bg-background px-[var(--layout-inner-padding)]"
                      >
                        <AccordionTrigger className="py-[calc(var(--layout-inner-padding)*0.75)] hover:no-underline">
                          <div className="flex min-w-0 flex-col items-start gap-0.5 text-left">
                            <span className="font-semibold text-foreground">{caseId}</span>
                            <span className="truncate text-xs text-muted-foreground">
                              {events.length} events · {caseTitle}
                            </span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-2">
                          <AuditEventList
                            events={events}
                            selectedEventId={selectedEventId}
                            onSelect={handleSelectEvent}
                            showCaseId={false}
                            emptyMessage="No entries in this request group."
                          />
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                ) : (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    {hasActiveFilters
                      ? "No grouped request traces match current filters."
                      : "No grouped request traces available right now."}
                  </p>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <div className="hidden xl:block">
          <div className="sticky top-4">
            <div
              key={selectedEvent?.id ?? "empty-sidebar"}
              className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200 motion-reduce:animate-none"
            >
              <AuditEntryDetails
                event={selectedEvent}
                isLoading={detailLoading}
                className="rounded-[var(--layout-outer-radius)] ring-0"
              />
            </div>
          </div>
        </div>
      </div>

      <Sheet
        open={detailSheetOpen && useDetailSheet && Boolean(selectedEvent)}
        onOpenChange={setDetailSheetOpen}
      >
        <SheetContent
          side="right"
          className="w-[min(100vw,31rem)] max-w-none gap-0 bg-background p-0 shadow-none xl:hidden"
          showCloseButton
        >
          <SheetHeader className="border-b px-4 py-3">
            <SheetTitle className="text-sm">Audit entry details</SheetTitle>
            <SheetDescription className="text-xs">
              Inspect event context, trace metadata, and structured payload.
            </SheetDescription>
          </SheetHeader>
          <div
            key={selectedEvent?.id ?? "empty-sheet"}
            className="overflow-y-auto p-3 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200 motion-reduce:animate-none"
          >
            <AuditEntryDetails
              event={selectedEvent}
              isLoading={detailLoading}
              className="rounded-[var(--layout-outer-radius)] border-0 ring-0"
            />
          </div>
        </SheetContent>
      </Sheet>

      {selectedEvent?.caseId ? (
        <div className="xl:hidden">
          <Link
            href={`/cases/${selectedEvent.caseId}`}
            className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Open selected case in workspace
          </Link>
        </div>
      ) : null}
    </div>
  )
}
