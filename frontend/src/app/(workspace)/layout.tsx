import type { ReactNode } from "react"

import { WorkspaceShell } from "@/components/app-shell/workspace-shell"

export default function WorkspaceLayout({
  children,
}: {
  children: ReactNode
}) {
  return <WorkspaceShell>{children}</WorkspaceShell>
}
