"use client"

import { useEffect, useMemo } from "react"
import Image from "next/image"
import { FileImage, FileText, Upload, X } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { UploadDropzone } from "@/components/ui/upload-dropzone"
import type { IntakeSourceType, RequestChannel } from "@/lib/types/case"
import { cn } from "@/lib/utils"

interface IntakeStepProps {
  mode: IntakeSourceType
  sourceText: string
  note: string
  requestChannel: RequestChannel
  selectedFiles: File[]
  processing: boolean
  error: string | null
  onModeChange: (value: IntakeSourceType) => void
  onSourceTextChange: (value: string) => void
  onNoteChange: (value: string) => void
  onRequestChannelChange: (value: RequestChannel) => void
  onSelectedFilesChange: (value: File[]) => void
}

function useObjectUrl(file: File | null) {
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

export function IntakeStep({
  mode,
  sourceText,
  note,
  requestChannel,
  selectedFiles,
  processing,
  error,
  onModeChange,
  onSourceTextChange,
  onNoteChange,
  onRequestChannelChange,
  onSelectedFilesChange,
}: IntakeStepProps) {
  const selectedFile = selectedFiles[0] ?? null
  const previewUrl = useObjectUrl(selectedFile)
  const requestChannelLabelByValue: Record<RequestChannel, string> = {
    portal: "Portal",
    email: "Email",
    teams: "Teams",
  }

  function handleFiles(files: File[]) {
    const nextFiles = files.slice(0, 1)
    onSelectedFilesChange(nextFiles)
    if (nextFiles.length > 0) {
      onModeChange("upload")
    }
  }

  function handleSourceText(value: string) {
    onSourceTextChange(value)
    if (value.trim().length > 0) {
      onModeChange("paste")
    } else if (selectedFiles.length > 0) {
      onModeChange("upload")
    }
  }

  return (
    <Card className="mx-auto max-w-5xl rounded-[var(--layout-outer-radius)] border-muted ring-0 animate-intake-stage-in">
      <CardHeader className="pb-4">
        <CardTitle>Provide request input</CardTitle>
        <CardDescription>
          Share what you have. We will extract structured fields and guide completion.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 px-[var(--layout-inner-padding)] pb-[var(--layout-inner-padding)]">
        {error ? <Alert variant="destructive">{error}</Alert> : null}

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.18fr)_minmax(16.5rem,0.82fr)]">
          <div className="space-y-4">
            <UploadDropzone
              multiple={false}
              disabled={processing}
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp"
              title="Upload file or image"
              description="Drop one file or click to browse. Accepted PDF, PNG, JPG, JPEG, GIF, and WEBP."
              icon={<Upload className="size-5" />}
              onFilesSelected={handleFiles}
            />

            {selectedFile ? (
              <div className="rounded-[var(--layout-outer-radius)] border p-[var(--layout-inner-padding)]">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{selectedFile.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {selectedFile.type || "Unknown type"} · {formatFileSize(selectedFile.size)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => onSelectedFilesChange([])}
                    >
                      <X className="size-4" />
                    </Button>
                  </div>
                </div>

                {selectedFile.type.startsWith("image/") && previewUrl ? (
                  <div className="mt-3 overflow-hidden rounded-[var(--layout-inner-radius)] border bg-background">
                    <Image
                      src={previewUrl}
                      alt={selectedFile.name}
                      width={1200}
                      height={800}
                      unoptimized
                      className="max-h-[160px] w-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="mt-3 flex items-center gap-2 rounded-[var(--layout-inner-radius)] border bg-background px-3 py-2.5 text-sm">
                    {selectedFile.type === "application/pdf" ? (
                      <FileText className="size-4 text-muted-foreground" />
                    ) : (
                      <FileImage className="size-4 text-muted-foreground" />
                    )}
                    <span className="truncate">Primary extraction asset selected</span>
                  </div>
                )}
              </div>
            ) : null}

            <div
              className={cn(
                "rounded-[var(--layout-outer-radius)] border bg-background p-[var(--layout-inner-padding)]",
                mode === "paste" && "border-primary/50",
              )}
            >
              <Textarea
                className="min-h-[170px] resize-none rounded-[var(--layout-inner-radius)] border-0 bg-transparent px-[calc(var(--layout-inner-padding)*0.65)] py-[calc(var(--layout-inner-padding)*0.6)] shadow-none focus-visible:ring-0"
                placeholder="Paste request text..."
                value={sourceText}
                onChange={(event) => handleSourceText(event.target.value)}
                onFocus={() => onModeChange("paste")}
              />
            </div>

          </div>

          <div className="space-y-4 rounded-[var(--layout-outer-radius)] border bg-background p-[var(--layout-inner-padding)]">
            <div>
              <p className="text-sm font-medium">Request metadata</p>
              <p className="text-xs text-muted-foreground">
                Add only the context that helps extraction. Everything else can be reviewed in the next step.
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Request channel
              </p>
              <Select
                value={requestChannel}
                onValueChange={(value) =>
                  onRequestChannelChange((value as RequestChannel) ?? "portal")
                }
              >
                <SelectTrigger className="w-full rounded-[var(--layout-inner-radius)] bg-background">
                  <span className="truncate">
                    {requestChannelLabelByValue[requestChannel] ?? "Portal"}
                  </span>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="portal">Portal</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="teams">Teams</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Supporting note
              </p>
              <Textarea
                className="min-h-[96px] resize-none rounded-[var(--layout-inner-radius)] bg-background"
                placeholder="Optional context for procurement reviewers"
                value={note}
                onChange={(event) => onNoteChange(event.target.value)}
              />
            </div>

            <Alert className="rounded-[var(--layout-inner-radius)]">
              Tip: include quantity, budget, and required-by date in the source to skip most manual edits.
            </Alert>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
