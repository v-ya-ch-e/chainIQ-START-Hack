"use client"

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

const WorkspaceHeaderActionsSetterContext = createContext<
  ((node: ReactNode | null) => void) | null
>(null)

const WorkspaceHeaderActionsNodeContext = createContext<ReactNode | null>(null)

export function WorkspaceHeaderActionsProvider({
  children,
}: {
  children: ReactNode
}) {
  const [node, setNode] = useState<ReactNode | null>(null)

  const setHeaderActions = useCallback((next: ReactNode | null) => {
    setNode(next)
  }, [])

  const setterValue = useMemo(() => setHeaderActions, [setHeaderActions])

  return (
    <WorkspaceHeaderActionsSetterContext.Provider value={setterValue}>
      <WorkspaceHeaderActionsNodeContext.Provider value={node}>
        {children}
      </WorkspaceHeaderActionsNodeContext.Provider>
    </WorkspaceHeaderActionsSetterContext.Provider>
  )
}

/** Stable setter — subscribing components do not re-render when header actions change. */
export function useSetWorkspaceHeaderActions() {
  const set = useContext(WorkspaceHeaderActionsSetterContext)
  if (!set) {
    throw new Error(
      "useSetWorkspaceHeaderActions must be used within WorkspaceHeaderActionsProvider",
    )
  }
  return set
}

export function WorkspaceHeaderActionsSlot() {
  const node = useContext(WorkspaceHeaderActionsNodeContext)
  if (!node) return null
  return (
    <div className="flex min-h-0 min-w-0 flex-1 items-center justify-end">
      <div className="min-w-0 w-full max-w-full">{node}</div>
    </div>
  )
}
