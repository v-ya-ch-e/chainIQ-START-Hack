"use client"

import { useCallback, useState } from "react"

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
}

export function usePipelineActionRunner() {
  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fallback, setFallback] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const clearNotices = useCallback(() => {
    setError(null)
    setFallback(null)
    setMessage(null)
  }, [])

  const runAction = useCallback(async <T>(options: PipelineActionOptions<T>) => {
    const { label, request, onSuccess, successMessage } = options

    setLoadingAction(label)
    setError(null)
    setFallback(null)
    setMessage(null)

    try {
      const result = await request()
      onSuccess?.(result)
      if (successMessage) {
        setMessage(successMessage)
      }
      return result
    } catch (actionError) {
      if (isRunsEndpointInstability(actionError)) {
        setFallback(errorMessage(actionError))
      } else {
        setError(errorMessage(actionError))
      }
      throw actionError
    } finally {
      setLoadingAction(null)
    }
  }, [])

  return {
    loadingAction,
    error,
    fallback,
    message,
    setError,
    setFallback,
    setMessage,
    clearNotices,
    runAction,
  }
}

