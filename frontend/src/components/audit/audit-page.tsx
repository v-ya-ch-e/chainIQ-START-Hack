"use client"

import { useState, useMemo } from "react"
import Link from "next/link"
import { Search, AlertTriangle, ShieldCheck, ShieldAlert, FileText, Cpu, Building2, TerminalSquare, AlertCircle, CheckCircle2, Info } from "lucide-react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Timeline, TimelineItem, TimelineIcon, TimelineContent } from "@/components/ui/timeline"
import { formatDateTime } from "@/lib/data/formatters"
import type { AuditFeedEvent } from "@/lib/types/case"

interface AuditPageProps {
  summary: Array<{ label: string; value: string; helper: string }>
  feed: AuditFeedEvent[]
}

const kindTone: Record<string, "info" | "success" | "warning" | "destructive" | "neutral"> = {
  source: "neutral",
  interpretation: "info",
  policy: "warning",
  supplier: "success",
  escalation: "destructive",
  audit: "info",
}

function getIconForKind(kind: string) {
  switch (kind) {
    case "source": return <FileText className="size-4" />
    case "interpretation": return <Cpu className="size-4" />
    case "policy": return <ShieldCheck className="size-4" />
    case "supplier": return <Building2 className="size-4" />
    case "escalation": return <ShieldAlert className="size-4" />
    default: return <TerminalSquare className="size-4" />
  }
}

function getLevelTone(level?: string) {
  if (level === "error") return "destructive"
  if (level === "warn") return "warning"
  if (level === "info") return "info"
  return "default"
}

function getLevelIcon(level?: string) {
  if (level === "error") return <AlertCircle className="size-4" />
  if (level === "warn") return <AlertTriangle className="size-4" />
  if (level === "info") return <Info className="size-4" />
  return <CheckCircle2 className="size-4" />
}

function AuditTimeline({ events, showCaseId = true }: { events: AuditFeedEvent[], showCaseId?: boolean }) {
  if (events.length === 0) {
    return <p className="py-4 text-sm text-muted-foreground">No audit entries found matching filters.</p>
  }

  return (
    <Timeline>
      {events.map((event) => (
        <TimelineItem key={event.id}>
          <TimelineIcon variant={getLevelTone(event.level) as any}>
            {getIconForKind(event.kind)}
          </TimelineIcon>
          <TimelineContent>
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm">{event.title}</span>
                  <StatusBadge label={event.kind} tone={kindTone[event.kind] ?? "neutral"} />
                  {event.level && event.level !== "info" && (
                    <StatusBadge label={event.level} tone={getLevelTone(event.level) as any} />
                  )}
                  {showCaseId && event.caseId && (
                    <Link href={`/cases/${event.caseId}`} className="text-xs font-medium text-primary hover:underline bg-primary/10 px-2 py-0.5 rounded-full">
                      {event.caseId}
                    </Link>
                  )}
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {event.description}
                </p>
                {event.category && (
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground opacity-70">
                    {event.category} {event.stepName && `· ${event.stepName}`}
                  </p>
                )}
              </div>
              <time className="text-xs font-medium tabular-nums text-muted-foreground whitespace-nowrap mt-1 sm:mt-0">
                {formatDateTime(event.timestamp)}
              </time>
            </div>
          </TimelineContent>
        </TimelineItem>
      ))}
    </Timeline>
  )
}

export function AuditPage({ summary, feed }: AuditPageProps) {
  const [query, setQuery] = useState("")
  const [kindFilter, setKindFilter] = useState("all")
  const [levelFilter, setLevelFilter] = useState("all")

  const filteredFeed = useMemo(() => {
    return feed.filter((event) => {
      const q = query.toLowerCase()
      const matchesSearch = !q || 
        event.title.toLowerCase().includes(q) || 
        event.description.toLowerCase().includes(q) || 
        event.caseId?.toLowerCase().includes(q)
      
      const matchesKind = kindFilter === "all" || event.kind === kindFilter
      const matchesLevel = levelFilter === "all" || event.level === levelFilter

      return matchesSearch && matchesKind && matchesLevel
    })
  }, [feed, query, kindFilter, levelFilter])

  const actionableEvents = filteredFeed.filter(
    (event) => event.level === "error" || event.level === "warn" || event.kind === "escalation"
  )

  const eventsByCase = filteredFeed.reduce((acc, event) => {
    if (!event.caseId) return acc
    if (!acc[event.caseId]) acc[event.caseId] = []
    acc[event.caseId].push(event)
    return acc
  }, {} as Record<string, AuditFeedEvent[]>)

  return (
    <div className="space-y-8">
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Audit"
          title="System Audit & Compliance Trace"
          description="Monitor automated sourcing agent health, trace compliance reasoning with full timeline context, and review systematic escalations."
        />
      </div>

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
          <CardTitle className="sr-only">Filters</CardTitle>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search event messages or request ID..."
                className="h-9 pl-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Select value={kindFilter} onValueChange={(val) => setKindFilter(val || "all")}>
                <SelectTrigger className="w-[160px] h-9">
                  <SelectValue placeholder="All kinds" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All kinds</SelectItem>
                  <SelectItem value="source">Source Data</SelectItem>
                  <SelectItem value="interpretation">Interpretation</SelectItem>
                  <SelectItem value="policy">Policy Rules</SelectItem>
                  <SelectItem value="supplier">Supplier Match</SelectItem>
                  <SelectItem value="escalation">Escalation</SelectItem>
                  <SelectItem value="audit">System Audit</SelectItem>
                </SelectContent>
              </Select>
              
              <Select value={levelFilter} onValueChange={(val) => setLevelFilter(val || "all")}>
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
            </div>
          </div>
        </CardHeader>
      </Card>

      <div className="animate-fade-in-up" style={{ animationDelay: "160ms" }}>
        <Tabs defaultValue="actionable" className="space-y-6">
          <TabsList>
            <TabsTrigger value="actionable">Actionable Events</TabsTrigger>
            <TabsTrigger value="full">Full Audit Log</TabsTrigger>
            <TabsTrigger value="by-request">Grouped by Request</TabsTrigger>
          </TabsList>

          <TabsContent value="actionable" className="space-y-4">
            <Card>
              <CardHeader className="pb-4">
                <CardTitle>Actionable Priority Trace</CardTitle>
                <p className="text-sm text-muted-foreground">Events triggering errors, warnings, or escalations across all cases.</p>
              </CardHeader>
              <CardContent className="pt-6">
                <AuditTimeline events={actionableEvents} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="full" className="space-y-4">
            <Card>
              <CardHeader className="pb-4">
                <CardTitle>Absolute Sequence Trace</CardTitle>
                <p className="text-sm text-muted-foreground">Complete interwoven timeline of all agent activities across cases.</p>
              </CardHeader>
              <CardContent className="pt-6">
                <AuditTimeline events={filteredFeed} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="by-request" className="space-y-4">
            <Card>
              <CardHeader className="pb-4 border-b">
                <CardTitle>Isolated Decision Traces</CardTitle>
                <p className="text-sm text-muted-foreground">Step-by-step logic tracing separated out by individual case workflow.</p>
              </CardHeader>
              <CardContent className="pt-4">
                {Object.keys(eventsByCase).length > 0 ? (
                  <Accordion type="single" collapsible className="w-full">
                    {Object.entries(eventsByCase).map(([caseId, caseEvents]) => (
                      <AccordionItem key={caseId} value={caseId} className="border bg-card rounded-lg mb-4 px-4 shadow-sm overflow-hidden">
                        <AccordionTrigger className="hover:no-underline py-4">
                          <div className="flex flex-col items-start gap-1 text-left">
                            <span className="font-semibold text-primary">{caseId}</span>
                            <span className="text-sm font-normal text-muted-foreground">
                              {caseEvents.length} events logged · {caseEvents[0]?.caseTitle}
                            </span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-6 border-t">
                          <AuditTimeline events={caseEvents} showCaseId={false} />
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                ) : (
                  <p className="text-sm text-muted-foreground py-4 text-center">No events found matching current filters.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
