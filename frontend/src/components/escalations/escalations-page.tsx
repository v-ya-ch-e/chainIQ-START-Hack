"use client"

import Link from "next/link"
import { ArrowRight, Search } from "lucide-react"
import { useMemo, useState } from "react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
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
import { cn } from "@/lib/utils"

interface EscalationsPageProps {
  items: QueueEscalationItem[]
}

export function EscalationsPage({ items }: EscalationsPageProps) {
  const openCount = items.filter((item) => item.status !== "resolved").length
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [blockingFilter, setBlockingFilter] = useState("all")
  const [selectedEscalationId, setSelectedEscalationId] = useState<string | null>(null)
  const [isReviewOpen, setIsReviewOpen] = useState(false)

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()

    return items.filter((item) => {
      const matchesQuery =
        !normalizedQuery ||
        item.caseId.toLowerCase().includes(normalizedQuery) ||
        item.title.toLowerCase().includes(normalizedQuery) ||
        item.ruleId.toLowerCase().includes(normalizedQuery) ||
        item.ruleLabel.toLowerCase().includes(normalizedQuery) ||
        item.escalateTo.toLowerCase().includes(normalizedQuery) ||
        item.businessUnit.toLowerCase().includes(normalizedQuery) ||
        item.country.toLowerCase().includes(normalizedQuery)

      const matchesStatus =
        statusFilter === "all" ? true : item.status === statusFilter

      const matchesBlocking =
        blockingFilter === "all"
          ? true
          : blockingFilter === "blocking"
            ? item.blocking
            : !item.blocking

      return matchesQuery && matchesStatus && matchesBlocking
    })
  }, [blockingFilter, items, query, statusFilter])

  const selectedItem =
    filteredItems.find((item) => item.escalationId === selectedEscalationId) ??
    items.find((item) => item.escalationId === selectedEscalationId) ??
    null

  function openReview(item: QueueEscalationItem) {
    setSelectedEscalationId(item.escalationId)
    setIsReviewOpen(true)
  }

  return (
    <>
      <div className="space-y-6">
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Escalation queue"
          title={`${openCount} open human-review actions`}
          description="Operational queue for blocked or conditionally proceedable cases."
        />
      </div>

      <Card className="animate-fade-in-up" style={{ animationDelay: "160ms" }}>
        <CardHeader className="space-y-4 border-b pb-4">
          <CardTitle>All escalations</CardTitle>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search case, rule, target role, business unit..."
                className="h-9 pl-9"
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <Select
                value={statusFilter}
                onValueChange={(value) => setStatusFilter(value ?? "all")}
              >
                <SelectTrigger className="h-9 w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={blockingFilter}
                onValueChange={(value) => setBlockingFilter(value ?? "all")}
              >
                <SelectTrigger className="h-9 w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All types</SelectItem>
                  <SelectItem value="blocking">Blocking only</SelectItem>
                  <SelectItem value="advisory">Advisory only</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[220px] px-4">Case</TableHead>
                  <TableHead className="min-w-[120px]">Rule</TableHead>
                  <TableHead className="min-w-[140px]">Escalate To</TableHead>
                  <TableHead className="min-w-[90px]">Blocking</TableHead>
                  <TableHead className="min-w-[90px]">Status</TableHead>
                  <TableHead className="min-w-[130px]">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No escalations match the current filters.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredItems.map((item) => (
                    <TableRow
                      key={item.escalationId}
                      data-state={
                        selectedEscalationId === item.escalationId ? "selected" : undefined
                      }
                      className="group cursor-pointer"
                      tabIndex={0}
                      role="button"
                      aria-label={`Review escalation ${item.escalationId}`}
                      onClick={() => openReview(item)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault()
                          openReview(item)
                        }
                      }}
                    >
                      <TableCell className="px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-medium">{item.caseId}</p>
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                              {item.title}
                            </p>
                          </div>
                          <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                        </div>
                      </TableCell>
                      <TableCell>
                        <StatusBadge label={item.ruleId} tone="info" />
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
                              : "neutral"
                          }
                        />
                      </TableCell>
                      <TableCell className="text-sm tabular-nums">
                        {formatDateTime(item.createdAt)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

        <div
          className="animate-fade-in-up grid gap-3 @xl/main:grid-cols-3"
          style={{ animationDelay: "240ms" }}
        >
          <QueueMetric
            label="Open escalations"
            value={openCount.toString()}
            helper="Unresolved workflow objects"
          />
          <QueueMetric
            label="Blocking cases"
            value={items
              .filter((item) => item.blocking && item.status !== "resolved")
              .length.toString()}
            helper="Autonomous progression paused"
          />
          <QueueMetric
            label="Distinct target roles"
            value={new Set(items.map((item) => item.escalateTo)).size.toString()}
            helper="Human stakeholders involved"
          />
        </div>
      </div>

      <Sheet open={isReviewOpen} onOpenChange={setIsReviewOpen}>
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl bg-white shadow-2xl"
        >
          <SheetHeader>
            <SheetTitle>
              {selectedItem ? `Review ${selectedItem.escalationId}` : "Review escalation"}
            </SheetTitle>
            <SheetDescription>
              Human review workspace for escalation triage and case handoff.
            </SheetDescription>
          </SheetHeader>

          {selectedItem ? (
            <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pb-4">
              <div className="rounded-lg border p-3">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Request snapshot
                </p>
                <p className="mt-1 text-sm font-semibold">{selectedItem.caseId}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {selectedItem.title}
                </p>
                <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <DetailRow label="Category" value={selectedItem.category} />
                  <DetailRow
                    label="Business unit"
                    value={selectedItem.businessUnit}
                  />
                  <DetailRow label="Country" value={selectedItem.country} />
                  <DetailRow
                    label="Created"
                    value={formatDateTime(selectedItem.createdAt)}
                  />
                </div>
              </div>

              <div className="rounded-lg border p-3">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Escalation context
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <StatusBadge label={selectedItem.ruleId} tone="info" />
                  <StatusBadge
                    label={selectedItem.blocking ? "blocking" : "advisory"}
                    tone={selectedItem.blocking ? "destructive" : "warning"}
                  />
                  <StatusBadge
                    label={selectedItem.status}
                    tone={
                      selectedItem.status === "resolved"
                        ? "success"
                        : "neutral"
                    }
                  />
                </div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {selectedItem.ruleLabel}
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {selectedItem.trigger}
                </p>
                <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <DetailRow label="Escalate to" value={selectedItem.escalateTo} />
                  <DetailRow
                    label="Recommendation state"
                    value={selectedItem.recommendationStatus.replaceAll("_", " ")}
                  />
                  <DetailRow
                    label="Suggested next action"
                    value={
                      selectedItem.blocking
                        ? `Coordinate decision with ${selectedItem.escalateTo}`
                        : `Document advisory input from ${selectedItem.escalateTo}`
                    }
                  />
                  <DetailRow
                    label="Last updated"
                    value={formatDateTime(selectedItem.lastUpdated)}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="px-4 py-2 text-sm text-muted-foreground">
              Select an escalation row to review details.
            </div>
          )}

          <SheetFooter className="border-t pt-3">
            {selectedItem ? (
              <>
                <Link
                  href={`/cases/${selectedItem.caseId}`}
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                >
                  Open full case
                </Link>
                <Link
                  href={`/cases/${selectedItem.caseId}?tab=escalations`}
                  className={cn(buttonVariants({ size: "sm" }))}
                >
                  Start review
                </Link>
              </>
            ) : null}
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/20 p-2.5">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm">{value}</p>
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
