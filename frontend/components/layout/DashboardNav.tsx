"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useClerk } from "@clerk/nextjs";
import { cn } from "@/lib/utils";

const CREATOR_LINKS = [
  { href: "/creator/overview", label: "Overview" },
  { href: "/creator/profile", label: "Profile" },
  { href: "/creator/portfolio", label: "Portfolio" },
  { href: "/creator/campaigns", label: "Campaigns" },
  { href: "/creator/applications", label: "Applications" },
  { href: "/creator/collaborations", label: "Collaborations" },
  { href: "/creator/payments", label: "Payments" },
  { href: "/creator/payout-method", label: "Payout method" },
  { href: "/creator/history", label: "History" },
  { href: "/creator/settings", label: "Settings" },
];

const BRAND_LINKS = [
  { href: "/brand/overview", label: "Overview" },
  { href: "/brand/profile", label: "Profile" },
  { href: "/brand/campaigns", label: "Campaigns" },
  { href: "/brand/campaigns/new", label: "New campaign" },
  { href: "/brand/creators", label: "Creators" },
  { href: "/brand/applications", label: "Applications" },
  { href: "/brand/collaborations", label: "Collaborations" },
  { href: "/brand/payments", label: "Payments" },
  { href: "/brand/history", label: "History" },
  { href: "/brand/settings", label: "Settings" },
];

const ADMIN_LINKS = [
  { href: "/admin/overview", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/campaigns", label: "Campaigns" },
  { href: "/admin/collaborations", label: "Collaborations" },
  { href: "/admin/reports", label: "Reports" },
  { href: "/admin/disputes", label: "Disputes" },
  { href: "/admin/payments", label: "Payment events" },
  { href: "/admin/audit", label: "Audit log" },
];

export function DashboardNav({ role }: { role: "creator" | "brand" | "admin" }) {
  const pathname = usePathname();
  const { signOut } = useClerk();
  const links =
    role === "creator"
      ? CREATOR_LINKS
      : role === "brand"
      ? BRAND_LINKS
      : ADMIN_LINKS;
  return (
    <aside className="flex w-full flex-col gap-1 border-b border-slate-200 bg-slate-50 p-3 md:w-56 md:border-b-0 md:border-r">
      <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {role === "admin" ? "Admin" : role === "brand" ? "Brand" : "Creator"}
      </p>
      <nav aria-label="Primary" className="flex flex-wrap md:flex-col">
        {links.map((l) => {
          const active =
            pathname === l.href || pathname.startsWith(l.href + "/");
          return (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-white font-medium text-slate-900 shadow-sm"
                  : "text-slate-600 hover:bg-white hover:text-slate-900",
              )}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
      <button
        type="button"
        onClick={() => signOut({ redirectUrl: "/sign-in" })}
        className="mt-2 rounded-md px-3 py-2 text-left text-sm text-slate-600 hover:bg-white hover:text-slate-900"
      >
        Sign out
      </button>
    </aside>
  );
}
