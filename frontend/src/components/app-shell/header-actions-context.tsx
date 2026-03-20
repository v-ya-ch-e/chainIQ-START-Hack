"use client"

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

interface HeaderActionsState {
  actions: ReactNode | null
  setActions: (node: ReactNode | null) => void
  titleExtra: ReactNode | null
  setTitleExtra: (node: ReactNode | null) => void
  breadcrumbOverride: string | null
  setBreadcrumbOverride: (label: string | null) => void
}

const HeaderActionsContext = createContext<HeaderActionsState>({
  actions: null,
  setActions: () => {},
  titleExtra: null,
  setTitleExtra: () => {},
  breadcrumbOverride: null,
  setBreadcrumbOverride: () => {},
})

export function HeaderActionsProvider({ children }: { children: ReactNode }) {
  const [actions, setActions] = useState<ReactNode | null>(null)
  const [titleExtra, setTitleExtra] = useState<ReactNode | null>(null)
  const [breadcrumbOverride, setBreadcrumbOverride] = useState<string | null>(null)
  const value = useMemo(
    () => ({ actions, setActions, titleExtra, setTitleExtra, breadcrumbOverride, setBreadcrumbOverride }),
    [actions, titleExtra, breadcrumbOverride],
  )
  return (
    <HeaderActionsContext.Provider value={value}>
      {children}
    </HeaderActionsContext.Provider>
  )
}

export function useHeaderActions() {
  return useContext(HeaderActionsContext)
}
