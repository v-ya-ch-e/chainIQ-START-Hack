import type { ReactNode } from "react"
import { cookies } from "next/headers"

import { WorkspaceShell } from "@/components/app-shell/workspace-shell"

export default async function WorkspaceLayout({
  children,
}: {
  children: ReactNode
}) {
  const sidebarCookie = (await cookies()).get("sidebar_state")?.value
  const defaultSidebarOpen = sidebarCookie === "false" ? false : true

  return (
    <WorkspaceShell defaultSidebarOpen={defaultSidebarOpen}>
      {children}
    </WorkspaceShell>
  )
}
