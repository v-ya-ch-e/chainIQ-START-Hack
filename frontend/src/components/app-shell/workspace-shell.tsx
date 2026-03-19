"use client"

import type { ReactNode } from "react"
import Image from "next/image"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  ChevronsUpDown,
  ChevronRight,
  LogOut,
  Settings,
  User,
} from "lucide-react"

import { AppNavigation } from "@/components/app-shell/nav-links"
import { PageTransition } from "@/components/shared/page-transition"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

interface WorkspaceShellProps {
  children: ReactNode
}

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  const pathname = usePathname()

  const crumbs = buildBreadcrumbs(pathname)

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
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
              className="h-8 w-auto shrink-0 group-data-[collapsible=icon]:hidden"
              priority
            />
            <Image
              src="/chainiq_logo.svg"
              alt="ChainIQ"
              width={473}
              height={187}
              className="hidden h-5 w-auto shrink-0 group-data-[collapsible=icon]:block"
              priority
            />
          </div>
        </SidebarHeader>

        <SidebarContent>
          <AppNavigation />
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger className="flex w-full items-center gap-2 rounded-lg p-2 text-left text-sm outline-none ring-sidebar-ring hover:bg-sidebar-accent focus-visible:ring-2">
                  <Avatar className="size-8 rounded-lg">
                    <AvatarFallback className="rounded-lg text-xs">
                      MA
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                    <span className="truncate font-medium">Max Analyst</span>
                    <span className="truncate text-xs text-muted-foreground">
                      Procurement Analyst
                    </span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4 group-data-[collapsible=icon]:hidden" />
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  side="top"
                  align="start"
                  sideOffset={8}
                  className="w-56"
                >
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>My Account</DropdownMenuLabel>
                    <DropdownMenuItem>
                      <User className="size-4" />
                      Profile
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Settings className="size-4" />
                      Settings
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                  <DropdownMenuSeparator />
                  <DropdownMenuGroup>
                    <DropdownMenuItem>
                      <LogOut className="size-4" />
                      Log out
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>

      </Sidebar>

      <SidebarInset className="min-h-0 overflow-hidden bg-white">
        <header className="flex h-(--header-height) shrink-0 items-center gap-3 border-b bg-white px-4">
          <SidebarTrigger className="-ml-1" />
          <nav aria-label="Breadcrumb" className="min-w-0">
            <ol className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground md:text-sm">
              {crumbs.map((crumb, index) => {
                const isLast = index === crumbs.length - 1

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
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="@container/main flex flex-col gap-2">
            <div className="m-3 flex min-w-0 flex-col gap-4 rounded-xl border bg-white p-4 shadow-sm md:m-4 md:gap-6 md:p-6">
              <PageTransition>{children}</PageTransition>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
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

  if (normalizedPath === "/escalations") {
    return [{ label: "Escalations" }]
  }

  if (normalizedPath === "/audit") {
    return [{ label: "Audit" }]
  }

  if (normalizedPath.startsWith("/cases/")) {
    const caseId = decodeURIComponent(normalizedPath.split("/")[2] ?? "").trim()
    return [
      { label: "Inbox", href: "/inbox" },
      { label: caseId ? `Case ${caseId}` : "Case Detail" },
    ]
  }

  return [
    { label: toTitleCase(normalizedPath.split("/").filter(Boolean).at(-1) ?? "Page") },
  ]
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
