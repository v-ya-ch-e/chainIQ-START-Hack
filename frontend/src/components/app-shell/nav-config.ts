import {
  BellRing,
  Database,
  Inbox,
  LayoutDashboard,
  ShieldCheck,
} from "lucide-react"

export interface NavItem {
  href: string
  label: string
  icon: typeof Inbox
  disabled?: boolean
}

export const navItems: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/escalations", label: "Escalations", icon: BellRing },
  { href: "/audit", label: "Audit", icon: ShieldCheck },
  { href: "/data", label: "Data", icon: Database },
]
