"use client"

import { createContext, useContext, useState, type ReactNode } from "react"

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
  return (
    <HeaderActionsContext.Provider value={{ actions, setActions, titleExtra, setTitleExtra, breadcrumbOverride, setBreadcrumbOverride }}>
      {children}
    </HeaderActionsContext.Provider>
  )
}

export function useHeaderActions() {
  return useContext(HeaderActionsContext)
}
