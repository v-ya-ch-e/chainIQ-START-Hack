"use client"

import type React from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  PauseCircle,
  ShieldAlert,
  Sparkles,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

type BadgeTone =
  | "default"
  | "info"
  | "success"
  | "amber"
  | "warning"
  | "destructive"
  | "neutral"

interface StatusBadgeProps {
  label: string
  tone?: BadgeTone
  className?: string
}

const toneClasses: Record<BadgeTone, string> = {
  default: "border-transparent bg-primary text-primary-foreground",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  destructive: "border-rose-200 bg-rose-50 text-rose-700",
  neutral: "border-border bg-muted text-muted-foreground",
}

const toneIcons: Partial<
  Record<BadgeTone, React.ComponentType<{ className?: string }>>
> = {
  info: Sparkles,
  success: CheckCircle2,
  warning: Clock3,
  destructive: ShieldAlert,
  neutral: PauseCircle,
  default: AlertTriangle,
}

export function StatusBadge({
  label,
  tone = "neutral",
  className,
}: StatusBadgeProps) {
  const Icon = toneIcons[tone]

  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium",
        toneClasses[tone],
        className,
      )}
    >
      {Icon ? <Icon className="size-3" /> : null}
      {label}
    </Badge>
  )
}
