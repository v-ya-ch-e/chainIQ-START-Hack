"use client"

import { useState } from "react"
import { Activity, Play, RefreshCw } from "lucide-react"

import { chainIqApi } from "@/lib/api/client"
import { SectionHeading } from "@/components/shared/section-heading"
import { JsonViewer } from "@/components/shared/json-viewer"
import {
  EmptyStateCard,
  ErrorStateCard,
  FallbackBanner,
} from "@/components/shared/state-cards"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

interface ApiClientShape {
  pipeline: {
    process: (payload: { request_id: string }) => Promise<unknown>
    processBatch: (payload: { request_ids: string[]; concurrency?: number }) => Promise<unknown>
    status: (requestId: string) => Promise<unknown>
    result: (requestId: string) => Promise<unknown>
    runs: (params?: Record<string, string | number | boolean>) => Promise<unknown>
    run: (runId: string) => Promise<unknown>
    audit: (
      requestId: string,
      params?: Record<string, string | number | boolean>,
    ) => Promise<unknown>
    auditSummary: (requestId: string) => Promise<unknown>
    steps: {
      fetch: (payload: { request_id: string }) => Promise<unknown>
      validate: (payload: { request_id: string }) => Promise<unknown>
      filter: (payload: { request_id: string }) => Promise<unknown>
      comply: (payload: { request_id: string }) => Promise<unknown>
      rank: (payload: { request_id: string }) => Promise<unknown>
      escalate: (payload: { request_id: string }) => Promise<unknown>
    }
  }
}

const client = chainIqApi as unknown as ApiClientShape

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) return error.message
  return "Unexpected pipeline error"
}

function isRunsEndpointInstability(error: unknown) {
  const message = errorMessage(error)
  return (
    message.includes("/api/logs/runs") ||
    message.includes("/api/logs/by-request") ||
    message.includes("Org Layer unreachable")
  )
}

export function PipelinePage() {
  const [requestId, setRequestId] = useState("REQ-000004")
  const [runId, setRunId] = useState("")
  const [batchIds, setBatchIds] = useState("REQ-000001,REQ-000004")
  const [concurrency, setConcurrency] = useState("5")

  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fallback, setFallback] = useState<string | null>(null)

  const [processResult, setProcessResult] = useState<unknown>(null)
  const [batchResult, setBatchResult] = useState<unknown>(null)
  const [statusResult, setStatusResult] = useState<unknown>(null)
  const [pipelineResult, setPipelineResult] = useState<unknown>(null)
  const [runsResult, setRunsResult] = useState<unknown>(null)
  const [runDetailResult, setRunDetailResult] = useState<unknown>(null)
  const [auditResult, setAuditResult] = useState<unknown>(null)
  const [summaryResult, setSummaryResult] = useState<unknown>(null)
  const [stepResult, setStepResult] = useState<unknown>(null)

  async function runAction<T>(label: string, fn: () => Promise<T>, onSuccess: (result: T) => void) {
    setLoadingAction(label)
    setError(null)
    setFallback(null)

    try {
      const result = await fn()
      onSuccess(result)
    } catch (actionError) {
      if (isRunsEndpointInstability(actionError)) {
        setFallback(errorMessage(actionError))
      } else {
        setError(errorMessage(actionError))
      }
    } finally {
      setLoadingAction(null)
    }
  }

  const stepActions: Array<{
    key: string
    label: string
    run: (payload: { request_id: string }) => Promise<unknown>
  }> = [
    { key: "fetch", label: "Run Fetch Step", run: client.pipeline.steps.fetch },
    { key: "validate", label: "Run Validate Step", run: client.pipeline.steps.validate },
    { key: "filter", label: "Run Filter Step", run: client.pipeline.steps.filter },
    { key: "comply", label: "Run Comply Step", run: client.pipeline.steps.comply },
    { key: "rank", label: "Run Rank Step", run: client.pipeline.steps.rank },
    { key: "escalate", label: "Run Escalate Step", run: client.pipeline.steps.escalate },
  ]

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Pipeline Ops"
        title="Workflow trigger and diagnostics"
        description="Trigger single/batch processing, inspect run status and results, and execute individual pipeline steps for debugging."
      />

      {error ? <ErrorStateCard title="Pipeline action failed" description={error} /> : null}
      {fallback ? (
        <FallbackBanner
          title="Runs endpoint degraded"
          detail={`Detected known instability around run log endpoints. Other pipeline actions remain usable. ${fallback}`}
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Single request</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={requestId}
              onChange={(event) => setRequestId(event.target.value)}
              placeholder="REQ-000004"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() =>
                  runAction(
                    "process",
                    () => client.pipeline.process({ request_id: requestId.trim() }),
                    setProcessResult,
                  )
                }
                disabled={loadingAction !== null || !requestId.trim()}
              >
                <Play className="size-3.5" />
                {loadingAction === "process" ? "Processing..." : "Process Request"}
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  runAction(
                    "status",
                    () => client.pipeline.status(requestId.trim()),
                    setStatusResult,
                  )
                }
                disabled={loadingAction !== null || !requestId.trim()}
              >
                <Activity className="size-3.5" />
                Status
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  runAction(
                    "result",
                    () => client.pipeline.result(requestId.trim()),
                    setPipelineResult,
                  )
                }
                disabled={loadingAction !== null || !requestId.trim()}
              >
                Result
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Batch process</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={batchIds}
              onChange={(event) => setBatchIds(event.target.value)}
              placeholder="REQ-000001,REQ-000004"
              className="min-h-20"
            />
            <Input
              value={concurrency}
              onChange={(event) => setConcurrency(event.target.value)}
              placeholder="Concurrency (1-20)"
              type="number"
            />
            <Button
              onClick={() =>
                runAction(
                  "batch",
                  () =>
                    client.pipeline.processBatch({
                      request_ids: batchIds
                        .split(",")
                        .map((entry) => entry.trim())
                        .filter(Boolean),
                      concurrency: Number(concurrency) || 5,
                    }),
                  setBatchResult,
                )
              }
              disabled={loadingAction !== null}
            >
              <Play className="size-3.5" />
              {loadingAction === "batch" ? "Submitting..." : "Process Batch"}
            </Button>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Runs and audit</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={runId}
              onChange={(event) => setRunId(event.target.value)}
              placeholder="Run ID (for run detail)"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() =>
                  runAction("runs", () => client.pipeline.runs({ limit: 25, skip: 0 }), setRunsResult)
                }
                disabled={loadingAction !== null}
              >
                List Runs
              </Button>
              <Button
                variant="outline"
                onClick={() => runAction("run", () => client.pipeline.run(runId.trim()), setRunDetailResult)}
                disabled={loadingAction !== null || !runId.trim()}
              >
                Get Run
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  runAction(
                    "audit",
                    () => client.pipeline.audit(requestId.trim(), { limit: 100, skip: 0 }),
                    setAuditResult,
                  )
                }
                disabled={loadingAction !== null || !requestId.trim()}
              >
                Audit Trail
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  runAction(
                    "summary",
                    () => client.pipeline.auditSummary(requestId.trim()),
                    setSummaryResult,
                  )
                }
                disabled={loadingAction !== null || !requestId.trim()}
              >
                Audit Summary
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Step runner</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Run individual pipeline steps for the active request ID.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {stepActions.map((entry) => (
                <Button
                  key={entry.key}
                  variant="outline"
                  onClick={() =>
                    runAction(
                      entry.key,
                      () => entry.run({ request_id: requestId.trim() }),
                      setStepResult,
                    )
                  }
                  disabled={loadingAction !== null || !requestId.trim()}
                >
                  {loadingAction === entry.key ? (
                    <RefreshCw className="size-3.5 animate-spin" />
                  ) : (
                    <Play className="size-3.5" />
                  )}
                  {entry.label}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        {processResult ? <JsonViewer title="Process Result" value={processResult} /> : null}
        {batchResult ? <JsonViewer title="Batch Result" value={batchResult} /> : null}
        {statusResult ? <JsonViewer title="Pipeline Status" value={statusResult} /> : null}
        {pipelineResult ? <JsonViewer title="Pipeline Result" value={pipelineResult} /> : null}
        {runsResult ? <JsonViewer title="Runs" value={runsResult} /> : null}
        {runDetailResult ? <JsonViewer title="Run Detail" value={runDetailResult} /> : null}
        {auditResult ? <JsonViewer title="Audit Trail" value={auditResult} /> : null}
        {summaryResult ? <JsonViewer title="Audit Summary" value={summaryResult} /> : null}
        {stepResult ? <JsonViewer title="Step Result" value={stepResult} /> : null}
      </section>

      {!processResult && !runsResult && !auditResult ? (
        <EmptyStateCard
          title="No pipeline operation executed"
          description="Run process, status, runs, or step actions to inspect workflow outputs here."
        />
      ) : null}
    </div>
  )
}
