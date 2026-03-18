"use client"

import type { ReactNode } from "react"
import Image from "next/image"
import {
  ChevronsUpDown,
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

      <SidebarInset className="min-h-0 overflow-hidden">
        <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <span className="text-sm font-medium">
            Sourcing Decision Cockpit
          </span>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="@container/main flex flex-col gap-2">
            <div className="flex min-w-0 flex-col gap-4 p-4 md:gap-6 md:p-6">
              <PageTransition>{children}</PageTransition>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
