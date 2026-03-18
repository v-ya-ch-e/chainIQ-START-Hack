import Link from "next/link"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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

export function AuditPage({ summary, feed }: AuditPageProps) {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Audit"
          title="Activity feed"
          description="Chronological trace of every audit event across all sourcing cases."
        />
      </div>

      <section className="animate-fade-in-up grid gap-3 @xl/main:grid-cols-2 @3xl/main:grid-cols-4" style={{ animationDelay: "80ms" }}>
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

      <Card className="animate-fade-in-up" style={{ animationDelay: "160ms" }}>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative space-y-0">
            {feed.map((event, index) => (
              <div key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
                <div className="flex flex-col items-center">
                  <div className="mt-1.5 size-2.5 shrink-0 rounded-full border-2 border-border bg-card" />
                  {index !== feed.length - 1 ? (
                    <div className="w-px flex-1 bg-border" />
                  ) : null}
                </div>

                <div className="min-w-0 flex-1 pb-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/cases/${event.caseId}`}
                      className="text-sm font-medium hover:underline"
                    >
                      {event.caseId}
                    </Link>
                    <StatusBadge
                      label={event.kind}
                      tone={kindTone[event.kind] ?? "neutral"}
                    />
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {formatDateTime(event.timestamp)}
                    </span>
                  </div>

                  <p className="mt-1 text-sm font-medium">{event.title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                    {event.description}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {event.caseTitle}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
