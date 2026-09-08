"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tabs, TabsList, TabsTab } from "@/components/ui/tabs";

const TABS = [
  { value: "tools", label: "AI Tools", href: "/ai-center/tools" },
  { value: "project", label: "AI Project", href: "/ai-center/project" },
  { value: "vendor-register", label: "Vendor Register", href: "/ai-center/vendor-register" },
];

export default function AiCenterLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const active = TABS.find((tab) => pathname.startsWith(tab.href))?.value ?? "tools";

  return (
    <div>
      <div className="mx-auto max-w-3xl">
        <Tabs value={active} className="mb-6">
          <TabsList>
            {TABS.map((tab) => (
              <TabsTab key={tab.value} value={tab.value} render={<Link href={tab.href} />} nativeButton={false}>
                {tab.label}
              </TabsTab>
            ))}
          </TabsList>
        </Tabs>
      </div>
      {children}
    </div>
  );
}
