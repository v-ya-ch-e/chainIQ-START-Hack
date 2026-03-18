import Link from "next/link"
import { ArrowUpRight } from "lucide-react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/data/formatters"
import type { QueueEscalationItem } from "@/lib/types/case"

interface EscalationsPageProps {
  items: QueueEscalationItem[]
}

export function EscalationsPage({ items }: EscalationsPageProps) {
  const openCount = items.filter((item) => item.status !== "resolved").length

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Escalation queue"
        title={`${openCount} open human-review actions`}
        description="Operational queue for blocked or conditionally proceedable cases."
      />

      <div className="grid gap-3 @xl/main:grid-cols-3">
        <QueueMetric
          label="Open escalations"
          value={openCount.toString()}
          helper="Unresolved workflow objects"
        />
        <QueueMetric
          label="Blocking cases"
          value={items.filter((item) => item.blocking).length.toString()}
          helper="Autonomous progression paused"
        />
        <QueueMetric
          label="Distinct target roles"
          value={new Set(items.map((item) => item.escalateTo)).size.toString()}
          helper="Human stakeholders involved"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All escalations</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[200px] px-4">Case</TableHead>
                  <TableHead className="min-w-[120px]">Rule</TableHead>
                  <TableHead className="min-w-[140px]">Escalate To</TableHead>
                  <TableHead className="min-w-[90px]">Blocking</TableHead>
                  <TableHead className="min-w-[90px]">Status</TableHead>
                  <TableHead className="min-w-[130px]">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.escalationId}>
                    <TableCell className="px-4 py-3">
                      <Link
                        href={`/cases/${item.caseId}`}
                        className="group flex items-center justify-between gap-2"
                      >
                        <div className="min-w-0">
                          <p className="font-medium">{item.caseId}</p>
                          <p className="mt-0.5 truncate text-xs text-muted-foreground">
                            {item.title}
                          </p>
                        </div>
                        <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusBadge label={item.rule} tone="info" />
                    </TableCell>
                    <TableCell className="text-sm">
                      {item.escalateTo}
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        label={item.blocking ? "blocking" : "advisory"}
                        tone={item.blocking ? "destructive" : "warning"}
                      />
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        label={item.status}
                        tone={
                          item.status === "resolved"
                            ? "success"
                            : item.status === "acknowledged"
                              ? "warning"
                              : "neutral"
                        }
                      />
                    </TableCell>
                    <TableCell className="text-sm tabular-nums">
                      {formatDateTime(item.createdAt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function QueueMetric({
  label,
  value,
  helper,
}: {
  label: string
  value: string
  helper: string
}) {
  return (
    <Card>
      <CardContent className="space-y-1.5 px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className="text-2xl font-semibold tabular-nums tracking-tight">
          {value}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {helper}
        </p>
      </CardContent>
    </Card>
  )
}
