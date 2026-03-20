"use client"

import { useMemo } from "react"
import { CalendarDays, ChevronDown, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

interface DateMenuInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  className?: string
}

function formatDisplayDate(value: string) {
  if (!value) return null
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString("en-CH", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

function isoDaysFromNow(days: number) {
  const now = new Date()
  now.setDate(now.getDate() + days)
  return now.toISOString().slice(0, 10)
}

export function DateMenuInput({
  value,
  onChange,
  placeholder = "Select date",
  disabled = false,
  className,
}: DateMenuInputProps) {
  const displayValue = formatDisplayDate(value)
  const quickOptions = useMemo(
    () => [
      { label: "Today", value: isoDaysFromNow(0) },
      { label: "In 7 days", value: isoDaysFromNow(7) },
      { label: "In 14 days", value: isoDaysFromNow(14) },
      { label: "In 30 days", value: isoDaysFromNow(30) },
    ],
    [],
  )

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        render={
          <Button
            type="button"
            variant="outline"
            className={cn(
              "h-9 w-full justify-between rounded-[var(--layout-inner-radius)] px-3",
              className,
            )}
          >
            <span
              className={cn(
                "flex min-w-0 items-center gap-2 truncate text-sm",
                !displayValue && "text-muted-foreground",
              )}
            >
              <CalendarDays className="size-4 shrink-0" />
              <span className="truncate">{displayValue ?? placeholder}</span>
            </span>
            <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
          </Button>
        }
      />
      <DropdownMenuContent
        align="start"
        sideOffset={6}
        className="w-[min(22rem,calc(100vw-3rem))] rounded-[var(--layout-outer-radius)] border p-[var(--layout-inner-padding)] shadow-none ring-0"
      >
        <DropdownMenuLabel className="px-0 pt-0 pb-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          Required by date
        </DropdownMenuLabel>

        <div className="space-y-2">
          <Input
            type="date"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            className="h-9 rounded-[var(--layout-inner-radius)]"
          />
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Quick picks
          </p>
        </div>

        <div className="mt-1 space-y-1">
          {quickOptions.map((option) => (
            <DropdownMenuItem
              key={option.label}
              className="justify-between rounded-[var(--layout-inner-radius)] px-2 py-1.5"
              onClick={() => onChange(option.value)}
            >
              <span>{option.label}</span>
              <span className="text-xs text-muted-foreground">
                {formatDisplayDate(option.value) ?? option.value}
              </span>
            </DropdownMenuItem>
          ))}
        </div>

        <DropdownMenuSeparator className="mx-0" />
        <DropdownMenuItem
          className="rounded-[var(--layout-inner-radius)] px-2 py-1.5"
          onClick={() => onChange("")}
          disabled={!value}
        >
          <X className="size-4" />
          Clear date
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
