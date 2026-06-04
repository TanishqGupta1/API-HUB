"use client";

import CursorTrail from "@/components/CursorTrail";
import SidebarNav from "@/components/SidebarNav";
import AdminTopBar from "@/components/AdminTopBar";
import { CustomerProvider } from "@/lib/customer-context";
import { useAdminGuard } from "@/components/portal/role-guard";
import type { ReactNode } from "react";

/**
 * Client shell for the admin layout.
 * Keeping this separate from the layout file lets layout.tsx be a server
 * component, which prevents Next.js from wrapping page children in an
 * unkeyed React array — eliminating a spurious "missing key" console warning.
 */
export default function AdminShell({ children }: { children: ReactNode }) {
  useAdminGuard();
  return (
    <CustomerProvider>
      <div className="shell">
        <SidebarNav />
        <div className="main">
          <AdminTopBar />
          {children}
        </div>
      </div>
      <CursorTrail />
    </CustomerProvider>
  );
}
