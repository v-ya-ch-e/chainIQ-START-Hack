"use client"

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export const topbarFilterControlClassName = "rounded-[var(--topbar-inner-radius)]"

export function TopbarFilters({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "ml-auto flex min-w-0 w-full flex-nowrap items-center justify-end gap-2 pr-2 [--topbar-inner-padding:0.25rem] [--topbar-inner-radius:var(--radius-md)] [--topbar-outer-radius:calc(var(--topbar-inner-radius)+var(--topbar-inner-padding))]",
        className,
      )}
    >
      {children}
    </div>
  )
}
