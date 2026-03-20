"use client"

import { useCallback, useState } from "react"
import { toast } from "sonner"

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

export interface PipelineActionOptions<T> {
  label: string
  request: () => Promise<T>
  onSuccess?: (result: T) => void
  successMessage?: string
  successDescription?: string
}

export type PipelineActionPhase = "running" | "success" | "error"

export interface PipelineActionLifecycle {
  label: string
  phase: PipelineActionPhase
  startedAt: string
  finishedAt?: string
  errorMessage?: string
}

export function usePipelineActionRunner() {
  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [actionLifecycleByLabel, setActionLifecycleByLabel] = useState<
    Record<string, PipelineActionLifecycle>
  >({})
  const [lastActionLifecycle, setLastActionLifecycle] =
    useState<PipelineActionLifecycle | null>(null)

  const runAction = useCallback(async <T>(options: PipelineActionOptions<T>) => {
    const { label, request, onSuccess, successMessage, successDescription } = options
    const startedAt = new Date().toISOString()

    setLoadingAction(label)
    setActionLifecycleByLabel((current) => ({
      ...current,
      [label]: {
        label,
        phase: "running",
        startedAt,
      },
    }))

    try {
      const result = await request()
      onSuccess?.(result)
      if (successMessage) {
        toast.success(successMessage, {
          description: successDescription,
        })
      }
      const completedLifecycle: PipelineActionLifecycle = {
        label,
        phase: "success",
        startedAt,
        finishedAt: new Date().toISOString(),
      }
      setActionLifecycleByLabel((current) => ({
        ...current,
        [label]: completedLifecycle,
      }))
      setLastActionLifecycle(completedLifecycle)
      return result
    } catch (actionError) {
      const failureMessage = errorMessage(actionError)
      if (isRunsEndpointInstability(actionError)) {
        toast.warning("Pipeline endpoint degraded", {
          description: failureMessage,
        })
      } else {
        toast.error("Action failed", {
          description: failureMessage,
        })
      }
      const failedLifecycle: PipelineActionLifecycle = {
        label,
        phase: "error",
        startedAt,
        finishedAt: new Date().toISOString(),
        errorMessage: failureMessage,
      }
      setActionLifecycleByLabel((current) => ({
        ...current,
        [label]: failedLifecycle,
      }))
      setLastActionLifecycle(failedLifecycle)
      throw actionError
    } finally {
      setLoadingAction(null)
    }
  }, [])

  const lastError = lastActionLifecycle?.phase === "error"
    ? lastActionLifecycle.errorMessage ?? null
    : null
  const isRunsDegraded = lastError != null && isRunsEndpointInstability(lastError)

  return {
    loadingAction,
    actionLifecycleByLabel,
    lastActionLifecycle,
    runAction,
    error: isRunsDegraded ? null : lastError,
    fallback: isRunsDegraded ? lastError : null,
  }
}
