"use client"

import Link from "next/link"
import { type ComponentProps, useMemo, useState } from "react"
import {
  AlertTriangle,
  Building2,
  Cpu,
  FileText,
  Filter,
  RefreshCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react"

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
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  Timeline,
  TimelineContent,
  TimelineIcon,
  TimelineItem,
} from "@/components/ui/timeline"
import { formatDateTime } from "@/lib/data/formatters"
import type {
  AuditFeedEvent,
  AuditFeedMeta,
  AuditSummaryMetric,
} from "@/lib/types/case"

interface AuditPageProps {
  summary: AuditSummaryMetric[]
  feed: AuditFeedEvent[]
  feedMeta: AuditFeedMeta
}

type StatusTone =
  | "default"
  | "info"
  | "success"
  | "amber"
  | "warning"
  | "destructive"
  | "neutral"
type TimelineVariant = ComponentProps<typeof TimelineIcon>["variant"]

const kindTone: Record<AuditFeedEvent["kind"], StatusTone> = {
  source: "neutral",
  interpretation: "info",
  policy: "warning",
  supplier: "success",
  escalation: "destructive",
  audit: "info",
}

const kindLabel: Record<AuditFeedEvent["kind"], string> = {
  source: "Source",
  interpretation: "Interpretation",
  policy: "Policy",
  supplier: "Supplier",
  escalation: "Escalation",
  audit: "Audit",
}

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

function getLevelTimelineVariant(level?: string): TimelineVariant {
  if (level === "error") return "destructive"
  if (level === "warn") return "warning"
  if (level === "info") return "info"
  return "default"
}

function getLevelBadgeTone(level?: string): StatusTone {
  if (level === "error") return "destructive"
  if (level === "warn") return "warning"
  if (level === "info") return "info"
  return "neutral"
}

function levelLabel(level?: string) {
  if (!level) return "unknown"
  if (level === "warn") return "warning"
  return level
}

function AuditTimeline({
  events,
  showCaseId = true,
  emptyMessage,
}: {
  events: AuditFeedEvent[]
  showCaseId?: boolean
  emptyMessage: string
}) {
  if (events.length === 0) {
    return <p className="py-4 text-sm text-muted-foreground">{emptyMessage}</p>
  }

  return (
    <Timeline>
      {events.map((event) => (
        <TimelineItem key={event.id}>
          <TimelineIcon variant={getLevelTimelineVariant(event.level)}>
            {getIconForKind(event.kind)}
          </TimelineIcon>
          <TimelineContent>
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-sm">{event.title}</span>
                  <StatusBadge
                    label={kindLabel[event.kind]}
                    tone={kindTone[event.kind]}
                  />
                  {event.level && event.level !== "info" && (
                    <StatusBadge
                      label={levelLabel(event.level)}
                      tone={getLevelBadgeTone(event.level)}
                    />
                  )}
                  {showCaseId && event.caseId && (
                    <Link
                      href={`/cases/${event.caseId}`}
                      className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary hover:underline"
                    >
                      {event.caseId}
                    </Link>
                  )}
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {event.description}
                </p>
                {event.category && (
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground opacity-70">
                    {event.category}
                    {event.stepName ? ` · ${event.stepName}` : ""}
                  </p>
                )}
              </div>
              <time className="mt-1 whitespace-nowrap text-xs font-medium tabular-nums text-muted-foreground sm:mt-0">
                {formatDateTime(event.timestamp)}
              </time>
            </div>
          </TimelineContent>
        </TimelineItem>
      ))}
    </Timeline>
  )
}

export function AuditPage({ summary, feed, feedMeta }: AuditPageProps) {
  const [query, setQuery] = useState("")
  const [kindFilter, setKindFilter] = useState("all")
  const [levelFilter, setLevelFilter] = useState("all")

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

      return matchesSearch && matchesKind && matchesLevel
    })
  }, [feed, kindFilter, levelFilter, query])

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
      .map((group) => ({
        ...group,
        events: group.events.sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
        ),
      }))
      .sort((a, b) => {
        const aLatest = a.events[0]?.timestamp ?? ""
        const bLatest = b.events[0]?.timestamp ?? ""
        return new Date(bLatest).getTime() - new Date(aLatest).getTime()
      })
  }, [filteredFeed])

  const activeFiltersCount =
    Number(kindFilter !== "all") +
    Number(levelFilter !== "all") +
    Number(query.trim().length > 0)
  const hasActiveFilters = activeFiltersCount > 0

  const resetFilters = () => {
    setQuery("")
    setKindFilter("all")
    setLevelFilter("all")
  }

  return (
    <div className="space-y-8">
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Audit"
          title="Audit and compliance overview"
          description="Track operational risk, inspect decision traces, and triage high-priority events quickly."
        />
      </div>

      {feedMeta.mode === "degraded" || feedMeta.isTruncated ? (
        <Card className="animate-fade-in-up border-amber-300 bg-amber-50/70 text-amber-900">
          <CardContent className="flex flex-col gap-1 pt-4 text-sm">
            <p className="flex items-center gap-2 font-medium">
              <AlertTriangle className="size-4" />
              Audit data quality notice
            </p>
            <p className="text-xs text-amber-800">
              {feedMeta.mode === "degraded"
                ? feedMeta.warning ?? "Audit feed is currently degraded."
                : "Audit feed is truncated to the current fetch limit."}{" "}
              Snapshot at {formatDateTime(feedMeta.asOf)}.
            </p>
          </CardContent>
        </Card>
      ) : null}

      <section
        className="animate-fade-in-up grid gap-3 @xl/main:grid-cols-2 @3xl/main:grid-cols-4"
        style={{ animationDelay: "80ms" }}
      >
        {summary.map((item) => (
          <Card key={item.label}>
            <CardContent className="space-y-1.5 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {item.label}
              </p>
              <p className="text-2xl font-semibold tabular-nums tracking-tight">
                {item.value}
              </p>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {item.helper}
              </p>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card className="animate-fade-in-up" style={{ animationDelay: "120ms" }}>
        <CardHeader className="border-b pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="size-4 text-muted-foreground" />
            Filters
          </CardTitle>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search request ID, case title, or event text..."
                className="h-9 pl-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Select
                value={kindFilter}
                onValueChange={(val) => setKindFilter(val || "all")}
              >
                <SelectTrigger className="w-[160px] h-9">
                  <SelectValue placeholder="All kinds" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All kinds</SelectItem>
                  <SelectItem value="source">Source</SelectItem>
                  <SelectItem value="interpretation">Interpretation</SelectItem>
                  <SelectItem value="policy">Policy</SelectItem>
                  <SelectItem value="supplier">Supplier</SelectItem>
                  <SelectItem value="escalation">Escalation</SelectItem>
                  <SelectItem value="audit">Audit</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={levelFilter}
                onValueChange={(val) => setLevelFilter(val || "all")}
              >
                <SelectTrigger className="w-[160px] h-9">
                  <SelectValue placeholder="All levels" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All levels</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                  <SelectItem value="warn">Warning</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                onClick={resetFilters}
                disabled={!hasActiveFilters}
              >
                <RefreshCcw className="mr-1.5 size-3.5" />
                Reset
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>
              Showing {filteredFeed.length} of {feedMeta.totalKnown} entries
            </span>
            {hasActiveFilters ? (
              <StatusBadge
                label={`${activeFiltersCount} filter${activeFiltersCount > 1 ? "s" : ""} active`}
                tone="info"
              />
            ) : null}
            {feedMeta.isTruncated ? (
              <StatusBadge label="truncated feed" tone="warning" />
            ) : null}
          </div>
        </CardHeader>
      </Card>

      <div className="animate-fade-in-up" style={{ animationDelay: "160ms" }}>
        <Tabs defaultValue="actionable" className="space-y-6">
          <TabsList>
            <TabsTrigger value="actionable">
              Actionable ({actionableEvents.length})
            </TabsTrigger>
            <TabsTrigger value="full">Full Log ({filteredFeed.length})</TabsTrigger>
            <TabsTrigger value="by-request">
              By Request ({eventsByCase.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="actionable" className="space-y-4">
            <Card>
              <CardHeader className="pb-4">
                <CardTitle>Actionable priority trace</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Events requiring attention: warnings, errors, and escalations.
                </p>
              </CardHeader>
              <CardContent className="pt-6">
                <AuditTimeline
                  events={actionableEvents}
                  emptyMessage={
                    hasActiveFilters
                      ? "No actionable events match current filters."
                      : "No actionable events available."
                  }
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="full" className="space-y-4">
            <Card>
              <CardHeader className="pb-4">
                <CardTitle>Full audit log</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Complete event sequence across all visible requests.
                </p>
              </CardHeader>
              <CardContent className="pt-6">
                <AuditTimeline
                  events={filteredFeed}
                  emptyMessage={
                    hasActiveFilters
                      ? "No events match current filters."
                      : "No audit entries available right now."
                  }
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="by-request" className="space-y-4">
            <Card>
              <CardHeader className="border-b pb-4">
                <CardTitle>Grouped by request</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Inspect each request timeline independently for focused review.
                </p>
              </CardHeader>
              <CardContent className="pt-4">
                {eventsByCase.length > 0 ? (
                  <Accordion type="multiple" className="w-full">
                    {eventsByCase.map(({ caseId, caseTitle, events }) => (
                      <AccordionItem
                        key={caseId}
                        value={caseId}
                        className="mb-4 overflow-hidden rounded-lg border bg-card px-4 shadow-sm"
                      >
                        <AccordionTrigger className="hover:no-underline py-4">
                          <div className="flex flex-col items-start gap-1 text-left">
                            <span className="font-semibold text-primary">{caseId}</span>
                            <span className="text-sm font-normal text-muted-foreground">
                              {events.length} events logged · {caseTitle}
                            </span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-6 border-t">
                          <AuditTimeline
                            events={events}
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
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
