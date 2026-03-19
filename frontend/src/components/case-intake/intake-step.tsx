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
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import type { IntakeSourceType, RequestChannel } from "@/lib/types/case"

interface IntakeStepProps {
  mode: IntakeSourceType
  sourceText: string
  note: string
  requestChannel: RequestChannel
  selectedFileNames: string[]
  processing: boolean
  error: string | null
  onModeChange: (value: IntakeSourceType) => void
  onSourceTextChange: (value: string) => void
  onNoteChange: (value: string) => void
  onRequestChannelChange: (value: RequestChannel) => void
  onSelectedFilesChange: (value: string[]) => void
  onExtract: () => void
}

export function IntakeStep({
  mode,
  sourceText,
  note,
  requestChannel,
  selectedFileNames,
  processing,
  error,
  onModeChange,
  onSourceTextChange,
  onNoteChange,
  onRequestChannelChange,
  onSelectedFilesChange,
  onExtract,
}: IntakeStepProps) {
  function handleFileInputChange(files: FileList | null) {
    if (!files) {
      onSelectedFilesChange([])
      return
    }
    onSelectedFilesChange(Array.from(files).map((file) => file.name))
  }

  const extractionButtonLabel =
    mode === "upload" ? "Analyze file" : "Extract information"

  return (
    <Card className="mx-auto max-w-4xl">
      <CardHeader>
        <CardTitle>Provide request input</CardTitle>
        <CardDescription>
          Paste text, upload a document, or switch to manual entry. The system will
          extract what it can and guide completion.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <Alert variant="destructive">{error}</Alert> : null}

        <Tabs
          value={mode}
          onValueChange={(value) => onModeChange((value as IntakeSourceType) ?? "paste")}
          className="space-y-4"
        >
          <TabsList>
            <TabsTrigger value="paste">Paste text</TabsTrigger>
            <TabsTrigger value="upload">Upload file</TabsTrigger>
            <TabsTrigger value="manual">Manual entry</TabsTrigger>
          </TabsList>

          <TabsContent value="paste" className="space-y-4">
            <Textarea
              placeholder="Paste email body, Teams message, or free-text request..."
              value={sourceText}
              onChange={(event) => onSourceTextChange(event.target.value)}
            />
          </TabsContent>

          <TabsContent value="upload" className="space-y-4">
            <label
              htmlFor="request-upload"
              className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 py-8 text-center"
            >
              <Upload className="mb-2 size-4 text-muted-foreground" />
              <p className="text-sm font-medium">Upload request document</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Drag and drop supported (PDF, DOCX, TXT, CSV)
              </p>
            </label>
            <Input
              id="request-upload"
              type="file"
              accept=".pdf,.docx,.txt,.csv"
              onChange={(event) => handleFileInputChange(event.target.files)}
              className="sr-only"
            />
            {selectedFileNames.length > 0 ? (
              <div className="rounded-lg border bg-muted/30 p-3 text-sm">
                {selectedFileNames.join(", ")}
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
              Manual entry starts with a minimal template and lets you fill fields
              directly in completion.
            </Alert>
            <Textarea
              placeholder="Optional: add initial context before manual completion"
              value={sourceText}
              onChange={(event) => onSourceTextChange(event.target.value)}
            />
          </TabsContent>
        </Tabs>

        <div className="grid gap-3 md:grid-cols-2">
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
                <SelectValue />
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
            <Input
              placeholder="Optional context"
              value={note}
              onChange={(event) => onNoteChange(event.target.value)}
            />
          </div>
        </div>

        <div className="flex items-center justify-end">
          <Button onClick={onExtract} disabled={processing}>
            {processing ? "Extracting..." : extractionButtonLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
