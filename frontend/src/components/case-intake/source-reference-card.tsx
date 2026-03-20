"use client"

import { useEffect, useMemo } from "react"
import Image from "next/image"
import { ChevronDown, FileImage, FileText, FileUp, Paperclip } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import type { IntakeSourceType } from "@/lib/types/case"
import { cn } from "@/lib/utils"

interface SourceReferenceCardProps {
  mode: IntakeSourceType
  sourceText: string
  selectedFile?: File | null
  note?: string
  sticky?: boolean
  compact?: boolean
  title?: string
  description?: string
}

function useObjectUrl(file: File | null | undefined) {
  const url = useMemo(() => {
    if (!file || !file.type.startsWith("image/")) return null
    return URL.createObjectURL(file)
  }, [file])

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [url])

  return url
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function sourceLabel(mode: IntakeSourceType) {
  if (mode === "upload") return "Upload context"
  if (mode === "manual") return "Initial context"
  return "Original request"
}

export function SourceReferenceCard({
  mode,
  sourceText,
  selectedFile,
  note,
  sticky = false,
  compact = false,
  title = "Source reference",
  description = "Compare extracted structure against the original request input.",
}: SourceReferenceCardProps) {
  const imageUrl = useObjectUrl(selectedFile)
  const isImage = Boolean(selectedFile?.type.startsWith("image/"))

  return (
    <Card
      className={cn(
        "h-fit rounded-[var(--layout-inner-radius)] border-muted ring-0 animate-intake-stage-in",
        sticky && "xl:sticky xl:top-0",
      )}
    >
      <CardHeader className={cn(compact ? "space-y-1 pb-3" : undefined)}>
        <CardTitle className={compact ? "text-base" : undefined}>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className={cn("space-y-4", compact && "space-y-3")}>
        {selectedFile ? (
          <div className="space-y-2 rounded-[var(--layout-outer-radius)] border bg-muted/10 p-[var(--layout-inner-padding)]">
            <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              <Paperclip className="size-3.5" />
              Uploaded asset
            </div>
            {isImage && imageUrl ? (
              <div className="overflow-hidden rounded-[var(--layout-inner-radius)] border bg-background">
                <Image
                  src={imageUrl}
                  alt={selectedFile.name}
                  width={1200}
                  height={800}
                  unoptimized
                  className={cn("w-full object-cover", compact ? "max-h-[140px]" : "max-h-[260px]")}
                />
              </div>
            ) : (
              <div className="flex items-center gap-3 rounded-[var(--layout-inner-radius)] border bg-background px-3 py-3">
                {selectedFile.type === "application/pdf" ? (
                  <FileText className="size-5 text-muted-foreground" />
                ) : (
                  <FileImage className="size-5 text-muted-foreground" />
                )}
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{selectedFile.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {selectedFile.type || "Unknown type"} · {formatFileSize(selectedFile.size)}
                  </p>
                </div>
              </div>
            )}
          </div>
        ) : mode === "upload" ? (
          <div className="rounded-[var(--layout-outer-radius)] border bg-muted/10 px-4 py-4 text-sm text-muted-foreground">
            <div className="mb-1 flex items-center gap-2 font-medium text-foreground">
              <FileUp className="size-4" />
              No uploaded asset
            </div>
            Add a PDF or image to give the parser a primary source document.
          </div>
        ) : null}

        <details className="group rounded-[var(--layout-outer-radius)] border bg-muted/10" open={!compact}>
          <summary className="flex list-none items-center justify-between gap-3 cursor-pointer px-3 py-2.5">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                {sourceLabel(mode)}
              </p>
              <p className="text-sm text-foreground">
                {sourceText.trim() ? "Source text available" : "No source text provided"}
              </p>
            </div>
            <ChevronDown className="size-4 transition-transform duration-200 group-open:rotate-180" />
          </summary>
          <div className="px-3 pb-3">
            <Textarea
              value={sourceText}
              readOnly
              className={cn("bg-background", compact ? "min-h-[120px]" : "min-h-[220px]")}
              placeholder={
                mode === "upload"
                  ? "Optional upload context will appear here."
                  : "No source text provided."
              }
            />
          </div>
        </details>

        {note ? (
          <div className="space-y-2 rounded-[var(--layout-outer-radius)] border bg-muted/10 p-[var(--layout-inner-padding)]">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Supporting note
            </p>
            <p className="text-sm leading-relaxed text-foreground">{note}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
