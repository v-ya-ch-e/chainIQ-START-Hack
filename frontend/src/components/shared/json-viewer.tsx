"use client"

import { useMemo, useState } from "react"
import { Check, Copy } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface JsonViewerProps {
  title: string
  value: unknown
  className?: string
  compact?: boolean
}

export function JsonViewer({ title, value, className, compact = false }: JsonViewerProps) {
  const [copied, setCopied] = useState(false)

  const text = useMemo(() => {
    try {
      return JSON.stringify(value, null, compact ? 0 : 2)
    } catch {
      return "Unable to serialize JSON payload."
    }
  }, [compact, value])

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Card className={className}>
      <CardHeader className="border-b pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle>{title}</CardTitle>
          <Button variant="outline" size="sm" onClick={copyJson}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-3">
        <pre className="max-h-[32rem] overflow-auto rounded-lg border bg-muted/25 p-3 text-xs leading-relaxed whitespace-pre-wrap break-all">
          {text}
        </pre>
      </CardContent>
    </Card>
  )
}
