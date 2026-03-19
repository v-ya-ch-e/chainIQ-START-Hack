import {
  BellRing,
  Inbox,
  LayoutDashboard,
  PlusSquare,
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
  { href: "/cases/new", label: "New Case", icon: PlusSquare },
  { href: "/escalations", label: "Escalations", icon: BellRing },
  { href: "/audit", label: "Audit", icon: ShieldCheck },
  // Data screen intentionally hidden from primary navigation for UX clarity.
]
