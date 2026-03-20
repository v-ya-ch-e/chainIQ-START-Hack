"use client"

import type { ReactNode } from "react"
import Image from "next/image"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight } from "lucide-react"

import { AppNavigation } from "@/components/app-shell/nav-links"
import { HeaderActionsProvider, useHeaderActions } from "@/components/app-shell/header-actions-context"
import { NavUser } from "@/components/app-shell/nav-user"
import { PageTransition } from "@/components/shared/page-transition"
import {
  WorkspaceHeaderActionsProvider,
  WorkspaceHeaderActionsSlot,
} from "@/components/app-shell/workspace-header-actions"
import { ThemeToggle } from "@/components/theme/theme-toggle"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

interface WorkspaceShellProps {
  children: ReactNode
  defaultSidebarOpen?: boolean
}

export function WorkspaceShell({
  children,
  defaultSidebarOpen = true,
}: WorkspaceShellProps) {
  const pathname = usePathname()

  const crumbs = buildBreadcrumbs(pathname)

  return (
    <WorkspaceHeaderActionsProvider>
    <HeaderActionsProvider>
      <SidebarProvider
        defaultOpen={defaultSidebarOpen}
        style={
          {
            "--sidebar-width": "calc(var(--spacing) * 72)",
            "--header-height": "calc(var(--spacing) * 12)",
            "--layout-inner-padding": "clamp(0.75rem, 1.2vw, 1rem)",
            "--layout-inner-radius": "calc(var(--radius) * 1.4)",
            "--layout-outer-radius":
              "calc(var(--layout-inner-radius) + var(--layout-inner-padding))",
            height: "100svh",
            minHeight: 0,
            overflow: "hidden",
          } as React.CSSProperties
        }
      >
        <Sidebar variant="inset" collapsible="icon">
          <SidebarHeader className="p-3">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <Image
                src="/chainiq_logo.svg"
                alt="ChainIQ"
                width={473}
                height={187}
                priority
                className="h-8 w-auto shrink-0 group-data-[collapsible=icon]:hidden"
              />
              <Image
                src="/chainiq_logo.svg"
                alt="ChainIQ"
                width={473}
                height={187}
                priority
                className="hidden h-5 w-auto shrink-0 group-data-[collapsible=icon]:block"
              />
            </div>
          </SidebarHeader>

          <SidebarContent>
            <AppNavigation />
          </SidebarContent>

          <SidebarFooter className="gap-2">
            <div className="flex justify-end px-0 group-data-[collapsible=icon]:justify-center">
              <ThemeToggle />
            </div>
            <NavUser
              user={{
                name: "Max Analyst",
                email: "max.analyst@chainiq.com",
                avatar: "",
              }}
            />
          </SidebarFooter>
        </Sidebar>

        <SidebarInset className="min-h-0 overflow-hidden bg-white">
          <ShellHeader crumbs={crumbs} />
          <div className="min-h-0 flex-1 overflow-y-auto p-[var(--layout-inner-padding)]">
            <div className="@container/main min-w-0 rounded-[var(--layout-inner-radius)]">
              <PageTransition>
                {children}
              </PageTransition>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </HeaderActionsProvider>
    </WorkspaceHeaderActionsProvider>
  )
}

type BreadcrumbItem = {
  label: string
  href?: string
}

function buildBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const normalizedPath = pathname.replace(/\/+$/, "") || "/"

  if (normalizedPath === "/") {
    return [{ label: "Overview" }]
  }

  if (normalizedPath === "/inbox") {
    return [{ label: "Inbox" }]
  }

  if (normalizedPath === "/intake") {
    return [{ label: "Intake" }]
  }

  if (normalizedPath === "/escalations") {
    return [{ label: "Escalations" }]
  }

  if (normalizedPath === "/audit") {
    return [{ label: "Audit" }]
  }

  if (normalizedPath === "/data") {
    return [{ label: "Data" }]
  }

  if (normalizedPath === "/cases/new") {
    return [
      { label: "Inbox", href: "/inbox" },
      { label: "New Case" },
    ]
  }

  if (normalizedPath.startsWith("/cases/")) {
    const segments = normalizedPath.split("/").filter(Boolean)
    if (segments[1] === "eval" && segments[2]) {
      return [
        { label: "Inbox", href: "/inbox" },
        { label: "Evaluation run", href: undefined },
      ]
    }
    const caseId = decodeURIComponent(segments[1] ?? "").trim()
    return [
      { label: "Inbox", href: "/inbox" },
      { label: caseId ? `Case ${caseId}` : "Case Detail" },
    ]
  }

  return [
    { label: toTitleCase(normalizedPath.split("/").filter(Boolean).at(-1) ?? "Page") },
  ]
}

function ShellHeader({ crumbs }: { crumbs: BreadcrumbItem[] }) {
  const { actions, titleExtra, breadcrumbOverride } = useHeaderActions()

  const effectiveCrumbs = breadcrumbOverride && crumbs.length > 0
    ? [
        ...crumbs.slice(0, -1),
        { ...crumbs[crumbs.length - 1], label: breadcrumbOverride },
      ]
    : crumbs

  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-3 border-b bg-white px-4">
      <SidebarTrigger className="-ml-1" />
      <nav aria-label="Breadcrumb" className="min-w-0">
        <ol className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground md:text-sm">
          {effectiveCrumbs.map((crumb, index) => {
            const isLast = index === effectiveCrumbs.length - 1

            return (
              <li
                key={crumb.href ?? `${crumb.label}-${index}`}
                className="flex min-w-0 items-center gap-1.5"
              >
                {index > 0 ? (
                  <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/70" />
                ) : null}
                {isLast || !crumb.href ? (
                  <span className="truncate font-medium text-foreground">
                    {crumb.label}
                  </span>
                ) : (
                  <Link
                    href={crumb.href}
                    className="truncate transition-colors hover:text-foreground"
                  >
                    {crumb.label}
                  </Link>
                )}
              </li>
            )
          })}
        </ol>
      </nav>
      {titleExtra ? (
        <div className="flex items-center gap-1.5">
          {titleExtra}
        </div>
      ) : null}
      <WorkspaceHeaderActionsSlot />
      {actions ? (
        <div className="ml-auto flex items-center gap-2">
          {actions}
        </div>
      ) : null}
    </header>
  )
}

function toTitleCase(value: string) {
  return value
    .replaceAll("-", " ")
    .replaceAll("_", " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}
