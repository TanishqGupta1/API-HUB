"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Package, History, Settings, Globe, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { usePortalGuard } from "@/components/portal/role-guard";

const NAV = [
  { href: "/dashboard",    label: "Dashboard",     icon: LayoutDashboard },
  { href: "/catalog",      label: "My Catalog",    icon: Package },
  { href: "/push-history", label: "Push History",  icon: History },
  { href: "/account",      label: "Account",       icon: Settings },
];

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  usePortalGuard();

  async function handleLogout() {
    await api("/api/auth/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-[#f9f7f4] flex">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 bg-white border-r border-[#ebe9e6] flex flex-col">
        {/* Brand */}
        <div className="px-5 py-5 border-b border-[#ebe9e6]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#1e4d92] flex items-center justify-center">
              <Globe className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="text-sm font-black text-[#1e1e24] tracking-tight">My Storefront</div>
              <div className="text-[10px] text-[#888894] font-medium">Self-Service Portal</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-semibold transition-all ${
                  active
                    ? "bg-[#1e4d92]/10 text-[#1e4d92]"
                    : "text-[#484852] hover:bg-[#f2f0ed] hover:text-[#1e1e24]"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-3 border-t border-[#ebe9e6]">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-semibold text-[#888894] hover:bg-[#f2f0ed] hover:text-[#1e1e24] transition-all"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  );
}
