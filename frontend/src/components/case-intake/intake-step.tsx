"use client"

import { Upload } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import type { IntakeSourceType, RequestChannel } from "@/lib/types/case"

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
  onExtract: () => void
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
  onExtract,
}: IntakeStepProps) {
  const requestChannelLabelByValue: Record<RequestChannel, string> = {
    portal: "Portal",
    email: "Email",
    teams: "Teams",
  }

  function handleFileInputChange(files: FileList | null) {
    if (!files) {
      onSelectedFilesChange([])
      return
    }
    onSelectedFilesChange(Array.from(files))
  }

  const extractionButtonLabel =
    mode === "upload" ? "Analyze file" : "Extract information"

  return (
    <Card className="mx-auto max-w-6xl">
      <CardHeader>
        <CardTitle>Provide request input</CardTitle>
        <CardDescription>
          Share what you have. We will extract structured fields and guide completion.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <Alert variant="destructive">{error}</Alert> : null}
        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-4">
            <Tabs
              value={mode}
              onValueChange={(value) =>
                onModeChange((value as IntakeSourceType) ?? "paste")
              }
              className="space-y-4"
            >
              <TabsList>
                <TabsTrigger value="paste">Paste text</TabsTrigger>
                <TabsTrigger value="upload">Upload file</TabsTrigger>
                <TabsTrigger value="manual">Manual entry</TabsTrigger>
              </TabsList>

              <TabsContent value="paste" className="space-y-4">
                <Textarea
                  className="min-h-[280px]"
                  placeholder="Paste email body, Teams message, or free-text request..."
                  value={sourceText}
                  onChange={(event) => onSourceTextChange(event.target.value)}
                />
              </TabsContent>

              <TabsContent value="upload" className="space-y-4">
                <label
                  htmlFor="request-upload"
                  className="flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 px-4 py-8 text-center"
                >
                  <Upload className="mb-2 size-4 text-muted-foreground" />
                  <p className="text-sm font-medium">Upload request document</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Drag and drop supported (PDF, PNG, JPG, JPEG, WEBP)
                  </p>
                </label>
                <Input
                  id="request-upload"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.webp"
                  onChange={(event) => handleFileInputChange(event.target.files)}
                  className="sr-only"
                />
                {selectedFiles.length > 0 ? (
                  <div className="rounded-lg border bg-muted/30 p-3 text-sm">
                    {selectedFiles.map((file) => file.name).join(", ")}
                  </div>
                ) : null}
                <Textarea
                  placeholder="Optional: add copied text or context note"
                  value={sourceText}
                  onChange={(event) => onSourceTextChange(event.target.value)}
                />
              </TabsContent>

              <TabsContent value="manual" className="space-y-4">
                <Alert>
                  Start with manual completion when no source text is available.
                </Alert>
                <Textarea
                  className="min-h-[220px]"
                  placeholder="Optional: add initial context before manual completion"
                  value={sourceText}
                  onChange={(event) => onSourceTextChange(event.target.value)}
                />
              </TabsContent>
            </Tabs>
          </div>

          <div className="space-y-4 rounded-lg border bg-muted/20 p-4">
            <div>
              <p className="text-sm font-medium">Request metadata</p>
              <p className="text-xs text-muted-foreground">
                Add optional context to improve extraction quality.
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
                <SelectTrigger className="w-full">
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
                className="min-h-[120px]"
                placeholder="Optional context for procurement reviewers"
                value={note}
                onChange={(event) => onNoteChange(event.target.value)}
              />
            </div>

            <Alert>
              Tip: include quantity, budget, and required-by date in source text to
              skip most manual edits.
            </Alert>

            <Button onClick={onExtract} disabled={processing} className="w-full">
              {processing ? "Extracting..." : extractionButtonLabel}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
