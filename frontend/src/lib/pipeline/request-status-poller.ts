"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { chainIqApi } from "@/lib/api/client"

export type PipelineLivePhase =
  | "idle"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "unknown"
  | "timed_out"

export interface RequestLiveState {
  requestId: string
  phase: PipelineLivePhase
  startedAt: string
  lastCheckedAt?: string
  finishedAt?: string
  statusPayload?: unknown
  error?: string
}

interface PollRequestOptions {
  initialPhase?: PipelineLivePhase
  intervalMs?: number
  timeoutMs?: number
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function statusCandidate(payload: unknown): string | null {
  const record = asRecord(payload)
  if (!record) return null
  const directCandidates = [
    record.status,
    record.state,
    record.pipeline_status,
    record.run_status,
    asRecord(record.latest_run)?.status,
    asRecord(record.latest_run)?.state,
    asRecord(record.run)?.status,
    asRecord(record.run)?.state,
  ]
  for (const value of directCandidates) {
    if (typeof value === "string" && value.trim()) {
      return value.trim().toLowerCase()
    }
  }
  return null
}

export function classifyPipelineStatus(payload: unknown): PipelineLivePhase {
  const candidate = statusCandidate(payload)
  if (!candidate) return "unknown"

  if (
    candidate.includes("not_started") ||
    candidate.includes("not started") ||
    candidate === "idle"
  ) {
    return "idle"
  }

  if (
    candidate.includes("complete") ||
    candidate.includes("success") ||
    candidate.includes("done") ||
    candidate.includes("resolved")
  ) {
    return "completed"
  }
  if (
    candidate.includes("fail") ||
    candidate.includes("error") ||
    candidate.includes("cancel") ||
    candidate.includes("aborted")
  ) {
    return "failed"
  }
  if (
    candidate.includes("queue") ||
    candidate.includes("pending") ||
    candidate.includes("scheduled") ||
    candidate.includes("waiting")
  ) {
    return "queued"
  }
  if (
    candidate.includes("running") ||
    candidate.includes("progress") ||
    candidate.includes("process") ||
    candidate.includes("execut")
  ) {
    return "running"
  }

  return "unknown"
}

function isTerminalPhase(phase: PipelineLivePhase) {
  return phase === "completed" || phase === "failed" || phase === "timed_out"
}

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) return error.message
  return "Pipeline status check failed."
}

export function useRequestStatusPoller() {
  const [requestLiveState, setRequestLiveState] = useState<
    Record<string, RequestLiveState>
  >({})
  const mountedRef = useRef(true)
  const tokenByRequestRef = useRef<Record<string, string>>({})

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const patchRequestState = useCallback(
    (requestId: string, patch: Partial<RequestLiveState>) => {
      if (!mountedRef.current) return
      setRequestLiveState((current) => {
        const existing = current[requestId]
        const next: RequestLiveState = {
          ...(existing ?? {}),
          requestId,
          phase: patch.phase ?? existing?.phase ?? "unknown",
          startedAt:
            patch.startedAt ?? existing?.startedAt ?? new Date().toISOString(),
          ...patch,
        }
        return {
          ...current,
          [requestId]: next,
        }
      })
    },
    [],
  )

  const clearRequestState = useCallback((requestId: string) => {
    if (!mountedRef.current) return
    setRequestLiveState((current) => {
      if (!(requestId in current)) return current
      const next = { ...current }
      delete next[requestId]
      return next
    })
  }, [])

  const stopPolling = useCallback((requestId: string) => {
    delete tokenByRequestRef.current[requestId]
  }, [])

  const startPolling = useCallback(
    async (requestId: string, options?: PollRequestOptions) => {
      const token = `${requestId}-${Date.now()}-${Math.random()}`
      tokenByRequestRef.current[requestId] = token

      const startedAt = new Date().toISOString()
      const intervalMs = options?.intervalMs ?? 2000
      const timeoutMs = options?.timeoutMs ?? 30_000
      const initialPhase = options?.initialPhase ?? "queued"
      let finalPhase: PipelineLivePhase = initialPhase

      patchRequestState(requestId, {
        requestId,
        phase: initialPhase,
        startedAt,
        lastCheckedAt: startedAt,
        error: undefined,
      })

      while (tokenByRequestRef.current[requestId] === token) {
        const now = Date.now()
        const elapsedMs = now - new Date(startedAt).getTime()
        if (elapsedMs > timeoutMs) {
          finalPhase = "timed_out"
          patchRequestState(requestId, {
            phase: "timed_out",
            finishedAt: new Date().toISOString(),
            lastCheckedAt: new Date().toISOString(),
          })
          break
        }

        try {
          const status = await chainIqApi.pipeline.status(requestId)
          const phase = classifyPipelineStatus(status)
          finalPhase = phase
          patchRequestState(requestId, {
            phase,
            statusPayload: status,
            lastCheckedAt: new Date().toISOString(),
            ...(isTerminalPhase(phase)
              ? { finishedAt: new Date().toISOString() }
              : {}),
          })
          if (isTerminalPhase(phase)) break
        } catch (pollError) {
          finalPhase = "unknown"
          patchRequestState(requestId, {
            phase: "unknown",
            lastCheckedAt: new Date().toISOString(),
            error: errorMessage(pollError),
          })
          break
        }

        await sleep(intervalMs)
      }
      return finalPhase
    },
    [patchRequestState],
  )

  return {
    requestLiveState,
    startPolling,
    stopPolling,
    patchRequestState,
    clearRequestState,
  }
}
