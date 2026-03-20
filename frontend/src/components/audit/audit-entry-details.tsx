"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import {
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  Layers3,
  MessageSquareText,
  TerminalSquare,
} from "lucide-react"

import { StatusBadge } from "@/components/shared/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDateTime, titleCase } from "@/lib/data/formatters"
import type { AuditFeedEvent } from "@/lib/types/case"
import { cn } from "@/lib/utils"

interface AuditEntryDetailsProps {
  event: AuditFeedEvent | null
  isLoading?: boolean
  showCaseLink?: boolean
  className?: string
}

type CopyTarget = "event" | "run"
type Tone =
  | "default"
  | "info"
  | "success"
  | "amber"
  | "warning"
  | "destructive"
  | "neutral"

const kindTone: Record<AuditFeedEvent["kind"], Tone> = {
  source: "neutral",
  interpretation: "info",
  policy: "warning",
  supplier: "success",
  escalation: "destructive",
  audit: "info",
}

function levelTone(level?: string): Tone {
  if (level === "error") return "destructive"
  if (level === "warn") return "warning"
  if (level === "info") return "info"
  return "neutral"
}

function prettySource(source?: string) {
  if (!source) return "-"
  return source
    .replaceAll("_", " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function stringifyDetails(details: Record<string, unknown> | null | undefined) {
  if (!details) return ""
  try {
    return JSON.stringify(details, null, 2)
  } catch {
    return "[Unserializable payload]"
  }
}

function formatPreview(text: string, maxLines = 8) {
  const lines = text.split("\n")
  if (lines.length <= maxLines) return text
  return `${lines.slice(0, maxLines).join("\n")}\n...`
}

function LoadingSkeleton({ className }: { className?: string }) {
  return (
    <Card
      className={cn(
        "rounded-[var(--layout-outer-radius,1.625rem)] border-border/80 shadow-none",
        className,
      )}
    >
      <CardHeader className="space-y-2 border-b px-[var(--layout-inner-padding,0.75rem)] pb-[var(--layout-inner-padding,0.75rem)]">
        <div className="h-5 w-44 animate-pulse rounded bg-muted" />
        <div className="h-4 w-36 animate-pulse rounded bg-muted" />
      </CardHeader>
      <CardContent className="space-y-4 px-[var(--layout-inner-padding,0.75rem)] py-[var(--layout-inner-padding,0.75rem)]">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <div className="h-3 w-16 animate-pulse rounded bg-muted" />
            <div className="h-4 w-full animate-pulse rounded bg-muted" />
          </div>
          <div className="space-y-2">
            <div className="h-3 w-16 animate-pulse rounded bg-muted" />
            <div className="h-4 w-full animate-pulse rounded bg-muted" />
          </div>
        </div>
        <div className="space-y-2">
          <div className="h-3 w-24 animate-pulse rounded bg-muted" />
          <div className="h-24 animate-pulse rounded-[var(--layout-inner-radius,0.875rem)] border bg-muted/40" />
        </div>
      </CardContent>
    </Card>
  )
}

function Field({
  label,
  value,
  monospace = false,
}: {
  label: string
  value: string
  monospace?: boolean
}) {
  return (
    <div className="space-y-1">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "min-w-0 break-words text-sm text-foreground",
          monospace && "font-mono text-xs",
        )}
      >
        {value}
      </p>
    </div>
  )
}

export function AuditEntryDetails({
  event,
  isLoading = false,
  showCaseLink = true,
  className,
}: AuditEntryDetailsProps) {
  const [expanded, setExpanded] = useState(false)
  const [copiedTarget, setCopiedTarget] = useState<CopyTarget | null>(null)
  const timerRef = useRef<number | null>(null)

  const detailsText = useMemo(() => stringifyDetails(event?.details), [event?.details])
  const detailPreview = useMemo(() => formatPreview(detailsText, 8), [detailsText])
  const detailLineCount = useMemo(
    () => (detailsText ? detailsText.split("\n").length : 0),
    [detailsText],
  )
  const canToggleDetails = detailLineCount > 8

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [])

  async function copyToClipboard(value: string, target: CopyTarget) {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedTarget(target)
      if (timerRef.current) window.clearTimeout(timerRef.current)
      timerRef.current = window.setTimeout(() => {
        setCopiedTarget(null)
      }, 1400)
    } catch {
      setCopiedTarget(null)
    }
  }

  if (isLoading) return <LoadingSkeleton className={className} />

  if (!event) {
    return (
      <Card
        className={cn(
          "rounded-[var(--layout-outer-radius,1.625rem)] border-border/80 shadow-none",
          className,
        )}
      >
        <CardContent
          className="flex min-h-44 items-center justify-center px-[var(--layout-inner-padding,0.75rem)] py-[var(--layout-inner-padding,0.75rem)]"
          aria-live="polite"
          role="status"
        >
          <div className="max-w-xs space-y-1.5 text-center">
            <p className="text-sm font-medium text-foreground">No audit event selected</p>
            <p className="text-sm text-muted-foreground">
              Select an event from the list to inspect full context and payload.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const details = detailsText || "No structured payload captured for this event."
  const visibleDetails = expanded ? details : detailPreview || details

  return (
    <Card
      className={cn(
        "rounded-[var(--layout-outer-radius,1.625rem)] border-border/80 shadow-none",
        className,
      )}
    >
      <CardHeader className="space-y-2 border-b px-[var(--layout-inner-padding,0.75rem)] pb-[var(--layout-inner-padding,0.75rem)]">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 space-y-1">
            <CardTitle className="text-base leading-snug">
              {event.title || "Audit event"}
            </CardTitle>
            <div className="flex flex-wrap items-center gap-1.5">
              <StatusBadge label={titleCase(event.kind)} tone={kindTone[event.kind]} />
              {event.level && event.level !== "info" ? (
                <StatusBadge label={titleCase(event.level)} tone={levelTone(event.level)} />
              ) : null}
            </div>
          </div>
          <time className="text-xs tabular-nums text-muted-foreground" suppressHydrationWarning>
            {formatDateTime(event.timestamp)}
          </time>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {showCaseLink ? (
            <Link
              href={`/cases/${event.caseId}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              Open case
              <ExternalLink className="size-3.5" />
            </Link>
          ) : null}
          {event.runId ? (
            <Link
              href={`/cases/eval/${event.runId}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              Open run
              <ExternalLink className="size-3.5" />
            </Link>
          ) : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => copyToClipboard(event.id, "event")}
          >
            {copiedTarget === "event" ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            {copiedTarget === "event" ? "Copied event id" : "Copy event id"}
          </Button>
          {event.runId ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(event.runId ?? "", "run")}
            >
              {copiedTarget === "run" ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copiedTarget === "run" ? "Copied run id" : "Copy run id"}
            </Button>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 px-[var(--layout-inner-padding,0.75rem)] py-[var(--layout-inner-padding,0.75rem)]">
        <section className="space-y-2">
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
            <Layers3 className="size-3.5" />
            Request and run context
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field
              label="Case"
              value={`${event.caseTitle || event.caseId} (${event.caseId})`}
            />
            <Field label="Run id" value={event.runId || "-"} monospace={Boolean(event.runId)} />
            <Field label="Category" value={event.category || "-"} />
            <Field label="Step" value={event.stepName || "-"} />
            <Field label="Source" value={prettySource(event.source)} />
            <Field label="Event id" value={event.id} monospace />
          </div>
        </section>

        <section className="space-y-2 border-t pt-[var(--layout-inner-padding,0.75rem)]">
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
            <MessageSquareText className="size-3.5" />
            Description
          </div>
          <p className="whitespace-pre-wrap text-sm text-foreground">
            {event.description || "-"}
          </p>
        </section>

        <section className="space-y-2 border-t pt-[var(--layout-inner-padding,0.75rem)]">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
              <TerminalSquare className="size-3.5" />
              Structured payload
            </div>
            {canToggleDetails ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setExpanded((current) => !current)}
                className="h-7 px-2 text-xs"
                aria-expanded={expanded}
                aria-controls={`audit-event-details-${event.id}`}
              >
                <ChevronDown className={cn("size-3.5 transition-transform", expanded && "rotate-180")} />
                {expanded ? "Collapse" : "Expand"}
              </Button>
            ) : null}
          </div>
          <div
            id={`audit-event-details-${event.id}`}
            className="overflow-auto rounded-[var(--layout-inner-radius,0.875rem)] border p-[calc(var(--layout-inner-padding,0.75rem)*0.9)]"
          >
            <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-foreground">
              {visibleDetails}
            </pre>
          </div>
          {canToggleDetails && !expanded ? (
            <p className="text-xs text-muted-foreground">Showing the first 8 lines.</p>
          ) : null}
        </section>
      </CardContent>
    </Card>
  )
}
