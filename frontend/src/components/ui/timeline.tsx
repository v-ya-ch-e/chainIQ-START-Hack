import * as React from "react"

import { cn } from "@/lib/utils"

const Timeline = React.forwardRef<
  HTMLOListElement,
  React.HTMLAttributes<HTMLOListElement>
>(({ className, ...props }, ref) => (
  <ol ref={ref} className={cn("relative border-s border-muted", className)} {...props} />
))
Timeline.displayName = "Timeline"

const TimelineItem = React.forwardRef<
  HTMLLIElement,
  React.HTMLAttributes<HTMLLIElement>
>(({ className, ...props }, ref) => (
  <li ref={ref} className={cn("mb-6 ms-8 last:mb-0", className)} {...props} />
))
TimelineItem.displayName = "TimelineItem"

const TimelineIcon = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { variant?: "default" | "primary" | "destructive" | "warning" | "success" | "info" }
>(({ className, variant = "default", ...props }, ref) => {
  const variants = {
    default: "bg-muted text-muted-foreground border-border",
    primary: "bg-primary text-primary-foreground border-primary",
    destructive: "bg-destructive text-destructive-foreground border-destructive",
    warning: "bg-warning text-warning-foreground border-warning",
    success: "bg-emerald-500 text-white border-emerald-500",
    info: "bg-blue-500 text-white border-blue-500",
  }
  
  // Custom mapping for our generic colors not explicitly in tailwind config initially
  const mappedVariant = variant === "warning" ? "bg-amber-500 text-white border-amber-500" :
                        variant === "destructive" ? "bg-red-500 text-white border-red-500" :
                        variants[variant]

  return (
    <span
      ref={ref}
      className={cn(
        "absolute -start-4 flex h-8 w-8 items-center justify-center rounded-full border ring-4 ring-background shadow-sm",
        mappedVariant,
        className
      )}
      {...props}
    />
  )
})
TimelineIcon.displayName = "TimelineIcon"

const TimelineContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col gap-1.5 rounded-lg border bg-card p-4 shadow-sm", className)} {...props} />
))
TimelineContent.displayName = "TimelineContent"

export { Timeline, TimelineItem, TimelineIcon, TimelineContent }
