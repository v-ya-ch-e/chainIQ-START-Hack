import { AlertTriangle, Database, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

export function EmptyStateCard({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <Card>
      <CardContent className="flex min-h-28 flex-col items-start justify-center gap-1.5 pt-4">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

export function ErrorStateCard({
  title,
  description,
  onRetry,
}: {
  title: string
  description: string
  onRetry?: () => void
}) {
  return (
    <Card className="border-rose-200 bg-rose-50/70 text-rose-900">
      <CardContent className="space-y-2 pt-4">
        <p className="flex items-center gap-2 text-sm font-medium">
          <AlertTriangle className="size-4" />
          {title}
        </p>
        <p className="text-sm text-rose-800">{description}</p>
        {onRetry ? (
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw className="size-3.5" />
            Retry
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function FallbackBanner({
  title,
  detail,
  onRetry,
}: {
  title: string
  detail: string
  onRetry?: () => void
}) {
  return (
    <Card className="border-amber-300 bg-amber-50/70 text-amber-900">
      <CardContent className="space-y-2 pt-4">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Database className="size-4" />
          {title}
        </p>
        <p className="text-sm text-amber-800">{detail}</p>
        {onRetry ? (
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw className="size-3.5" />
            Retry
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}
