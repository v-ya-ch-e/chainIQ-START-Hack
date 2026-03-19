"use client"

import { Badge } from "@/components/ui/badge"
import type { IntakeFieldStatus } from "@/lib/types/case"

interface FieldStatusBadgeProps {
  status: IntakeFieldStatus
}

const STATUS_LABEL: Record<IntakeFieldStatus, string> = {
  confident: "Extracted",
  inferred: "Inferred",
  missing: "Missing",
  needs_review: "Needs review",
}

const STATUS_VARIANT: Record<
  IntakeFieldStatus,
  "secondary" | "destructive" | "outline"
> = {
  confident: "secondary",
  inferred: "outline",
  missing: "destructive",
  needs_review: "outline",
}

export function FieldStatusBadge({ status }: FieldStatusBadgeProps) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>
}
