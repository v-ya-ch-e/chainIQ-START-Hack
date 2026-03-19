import Link from "next/link"
import { AlertTriangle, ArrowRight } from "lucide-react"

import { formatDateTime } from "@/lib/data/formatters"
import { MetricCard } from "@/components/shared/metric-card"
import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type {
  CaseListItem,
  DashboardDataState,
  DashboardMetric,
} from "@/lib/types/case"

interface OverviewPageProps {
  metrics: DashboardMetric[]
  cases: CaseListItem[]
  dataState: DashboardDataState
}

export function OverviewPage({ metrics, cases, dataState }: OverviewPageProps) {
  const escalatedCases = cases.filter(
    (entry) => entry.escalationStatus !== "none",
  )
  const blockedCases = cases.filter(
    (entry) => entry.recommendationStatus === "cannot_proceed",
  )

  return (
    <div className="space-y-8">
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Overview"
          title="Sourcing Decision Cockpit"
          description="Operational summary across all sourcing cases. Drill into the Inbox for triage or Escalations for blocked cases."
        />
      </div>

      {dataState.mode === "stale" ? (
        <Card className="animate-fade-in-up border-amber-300 bg-amber-50/70 text-amber-900" style={{ animationDelay: "40ms" }}>
          <CardContent className="flex flex-col gap-1 pt-4">
            <p className="flex items-center gap-2 text-sm font-medium">
              <AlertTriangle className="size-4" />
              Backend temporarily unavailable. Showing last successful snapshot.
            </p>
            <p className="text-xs text-amber-800">
              Snapshot as of {formatDateTime(dataState.asOf)}.
              {dataState.reason ? ` ${dataState.reason}` : ""}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <section className="animate-fade-in-up grid gap-3 @xl/main:grid-cols-2 @3xl/main:grid-cols-4" style={{ animationDelay: "80ms" }}>
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            helper={metric.helper}
            tone={metric.tone}
          />
        ))}
      </section>

      <section className="animate-fade-in-up grid gap-6 @3xl/main:grid-cols-2" style={{ animationDelay: "160ms" }}>
        <Card>
          <CardHeader>
            <CardTitle>Blocked cases</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {blockedCases.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No blocked cases at this time.
              </p>
            ) : (
              blockedCases.map((entry) => (
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
                  </div>
                  <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent escalations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {escalatedCases.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No escalations at this time.
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
