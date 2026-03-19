"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ArrowRight, Search } from "lucide-react"

import { SectionHeading } from "@/components/shared/section-heading"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatCurrency, formatDate } from "@/lib/data/formatters"
import type { CaseListItem } from "@/lib/types/case"
import { cn } from "@/lib/utils"

interface InboxPageProps {
  cases: CaseListItem[]
}

const statusOptions = [
  { value: "all", label: "All statuses" },
  { value: "pending_review", label: "Pending review" },
  { value: "recommended", label: "Recommended" },
  { value: "evaluated", label: "Evaluated" },
  { value: "escalated", label: "Escalated" },
]

export function InboxPage({ cases }: InboxPageProps) {
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [attentionOnly, setAttentionOnly] = useState(false)

  const filteredCases = useMemo(() => {
    return cases.filter((entry) => {
      const normalizedQuery = query.trim().toLowerCase()
      const matchesQuery =
        !normalizedQuery ||
        entry.requestId.toLowerCase().includes(normalizedQuery) ||
        entry.title.toLowerCase().includes(normalizedQuery) ||
        entry.businessUnit.toLowerCase().includes(normalizedQuery) ||
        entry.countryLabel.toLowerCase().includes(normalizedQuery) ||
        entry.supplierLabel.toLowerCase().includes(normalizedQuery)

      const matchesStatus =
        statusFilter === "all" ? true : entry.status === statusFilter

      const matchesAttention = attentionOnly ? entry.needsAttention : true

      return matchesQuery && matchesStatus && matchesAttention
    })
  }, [attentionOnly, cases, query, statusFilter])

  return (
    <div className="space-y-6">
      <div className="animate-fade-in-up">
        <SectionHeading
          eyebrow="Inbox"
          title="Case triage queue"
          description="Search, filter, and drill into individual sourcing cases."
        />
      </div>

      <Card className="animate-fade-in-up" style={{ animationDelay: "80ms" }}>
        <CardHeader className="border-b pb-4">
          <CardTitle className="sr-only">Filters</CardTitle>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search request ID, title, supplier, business unit, country..."
                className="h-9 pl-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Select
                value={statusFilter}
                onValueChange={(v) => setStatusFilter(v ?? "all")}
              >
                <SelectTrigger className="w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={attentionOnly}
                  onCheckedChange={(checked) =>
                    setAttentionOnly(checked === true)
                  }
                />
                Needs attention only
              </label>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[200px] px-4">
                    Request
                  </TableHead>
                  <TableHead className="min-w-[120px]">Category</TableHead>
                  <TableHead className="min-w-[80px]">Country</TableHead>
                  <TableHead className="min-w-[100px]">Budget</TableHead>
                  <TableHead className="min-w-[100px]">Required By</TableHead>
                  <TableHead className="min-w-[100px]">Status</TableHead>
                  <TableHead className="min-w-[120px]">
                    Recommendation
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCases.map((entry) => {
                  const recommendationTone =
                    entry.recommendationStatus === "proceed"
                      ? "success"
                      : entry.recommendationStatus ===
                          "proceed_with_conditions"
                        ? "warning"
                        : "destructive"

                  return (
                    <TableRow
                      key={entry.requestId}
                      className={cn(
                        "group",
                        entry.needsAttention &&
                          "border-l-2 border-l-amber-400",
                      )}
                    >
                      <TableCell className="px-4 py-3">
                        <Link
                          href={`/cases/${entry.requestId}`}
                          className="flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0">
                            <p className="font-medium">{entry.requestId}</p>
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                              {entry.title}
                            </p>
                          </div>
                          <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                        </Link>
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.category}
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.countryLabel}
                      </TableCell>
                      <TableCell className="text-sm font-medium tabular-nums">
                        {formatCurrency(entry.budgetAmount, entry.currency)}
                      </TableCell>
                      <TableCell className="text-sm tabular-nums">
                        {formatDate(entry.requiredByDate)}
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={entry.status.replaceAll("_", " ")}
                          tone={entry.needsAttention ? "warning" : "neutral"}
                        />
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          label={entry.recommendationStatus.replaceAll(
                            "_",
                            " ",
                          )}
                          tone={recommendationTone}
                        />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
