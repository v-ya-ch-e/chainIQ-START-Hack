import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface MetricCardProps {
  label: string
  value: string | number
  helper: string
  tone?: "default" | "success" | "warning" | "destructive" | "info"
}

const toneClasses = {
  default: "text-foreground",
  success: "text-emerald-700",
  warning: "text-amber-700",
  destructive: "text-rose-700",
  info: "text-blue-700",
}

export function MetricCard({
  label,
  value,
  helper,
  tone = "default",
}: MetricCardProps) {
  return (
    <Card>
      <CardContent className="space-y-1.5 px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className={cn("text-2xl font-semibold tabular-nums tracking-tight", toneClasses[tone])}>
          {value}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">{helper}</p>
      </CardContent>
    </Card>
  )
}
