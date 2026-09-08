"use client"

import * as React from "react"
import { Tabs as TabsPrimitive } from "@base-ui/react/tabs"

import { cn } from "@/lib/utils"

// Used in route-driven mode, not the primitive's own internal
// value/onValueChange state: the AI Center layout computes `value` from
// usePathname() and passes no onValueChange - each Tab is a real Link, so
// clicking navigates via Next.js routing, which changes the pathname,
// which recomputes the active tab on the next render. There is no
// Tabs.Panel here - each "panel" is a real route's own page content, not
// a conditionally-rendered sibling.
const Tabs = TabsPrimitive.Root

function TabsList({ className, ...props }: TabsPrimitive.List.Props) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn("inline-flex items-center gap-1 border-b border-border", className)}
      {...props}
    />
  )
}

function TabsTab({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-tab"
      className={cn(
        "relative -mb-px px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground data-[active]:text-foreground data-[active]:after:absolute data-[active]:after:inset-x-0 data-[active]:after:-bottom-px data-[active]:after:h-0.5 data-[active]:after:rounded-full data-[active]:after:bg-primary",
        className
      )}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTab }
