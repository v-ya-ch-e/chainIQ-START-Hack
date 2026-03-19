import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "rounded-lg border px-3 py-2 text-sm",
  {
    variants: {
      variant: {
        default: "border-border bg-background text-foreground",
        warning: "border-amber-200 bg-amber-50/70 text-amber-900",
        destructive: "border-rose-200 bg-rose-50/70 text-rose-900",
        success: "border-emerald-200 bg-emerald-50/70 text-emerald-900",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      role="status"
      data-slot="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Alert }
