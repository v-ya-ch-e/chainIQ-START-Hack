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
    <div className="flex min-h-0 min-w-0 flex-1 basis-0 items-center">
      <div className="min-h-0 min-w-0 w-full max-w-full overflow-x-auto overscroll-x-contain [scrollbar-width:thin]">
        <div className="ml-auto flex w-max min-w-0 flex-nowrap items-center gap-3">
          {node}
        </div>
      </div>
    </div>
  )
}
