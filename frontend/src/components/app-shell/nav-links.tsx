"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { navItems } from "@/components/app-shell/nav-config"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuBadge,
} from "@/components/ui/sidebar"

export function AppNavigation() {
  const pathname = usePathname()

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Navigation</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu className="gap-1.5">
          {navItems.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href)
            const Icon = item.icon

            return (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton
                  isActive={active}
                  tooltip={item.label}
                  disabled={item.disabled}
                  render={
                    item.disabled ? (
                      <span />
                    ) : (
                      <Link href={item.href} />
                    )
                  }
                >
                  <Icon />
                  <span>{item.label}</span>
                </SidebarMenuButton>
                {item.disabled ? (
                  <SidebarMenuBadge className="text-[10px] uppercase tracking-widest opacity-60">
                    Soon
                  </SidebarMenuBadge>
                ) : null}
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
