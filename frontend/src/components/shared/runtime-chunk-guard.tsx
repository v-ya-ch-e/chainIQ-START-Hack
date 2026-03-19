"use client"

import { useEffect } from "react"

const RELOAD_GUARD_KEY = "__chainiq_chunk_reload_once__"

function textFromUnknown(value: unknown): string {
  if (value instanceof Error && value.message) return value.message
  if (typeof value === "string") return value
  return ""
}

function isChunkAssetUrl(value: string | null | undefined): boolean {
  if (!value) return false
  return value.includes("/_next/static/chunks/")
}

function shouldRecoverFromErrorValue(value: unknown): boolean {
  const message = textFromUnknown(value)
  if (!message) return false

  return (
    message.includes("ChunkLoadError") ||
    message.includes("Loading chunk") ||
    message.includes("Loading CSS chunk") ||
    message.includes("Failed to fetch dynamically imported module") ||
    message.includes("/_next/static/chunks/") ||
    message.includes("[root-of-the-server]")
  )
}

function shouldRecoverFromErrorEvent(event: ErrorEvent): boolean {
  if (shouldRecoverFromErrorValue(event.error)) return true
  if (shouldRecoverFromErrorValue(event.message)) return true

  const target = event.target
  if (target instanceof HTMLScriptElement) {
    return isChunkAssetUrl(target.src)
  }
  if (target instanceof HTMLLinkElement) {
    return isChunkAssetUrl(target.href)
  }
  return false
}

function shouldRecoverFromRejection(event: PromiseRejectionEvent): boolean {
  if (shouldRecoverFromErrorValue(event.reason)) return true
  return false
}

function triggerRecoverReload() {
  try {
    if (sessionStorage.getItem(RELOAD_GUARD_KEY)) {
      return
    }
    sessionStorage.setItem(RELOAD_GUARD_KEY, String(Date.now()))
  } catch {
    // Ignore storage issues and continue to reload.
  }

  window.location.reload()
}

export function RuntimeChunkGuard() {
  useEffect(() => {
    const onError = (event: Event) => {
      if (event instanceof ErrorEvent && shouldRecoverFromErrorEvent(event)) {
        triggerRecoverReload()
      }
    }
    const onRejection = (event: PromiseRejectionEvent) => {
      if (shouldRecoverFromRejection(event)) {
        triggerRecoverReload()
      }
    }

    window.addEventListener("error", onError, true)
    window.addEventListener("unhandledrejection", onRejection)
    return () => {
      window.removeEventListener("error", onError, true)
      window.removeEventListener("unhandledrejection", onRejection)
    }
  }, [])

  return null
}
