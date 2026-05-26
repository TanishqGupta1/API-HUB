"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { api } from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

export function NotificationBell() {
  const [count, setCount] = useState(0);

  const load = async () => {
    try {
      const data = await api<{ count: number }>("/api/notifications/unread-count");
      setCount(data.count);
    } catch {
      // never break the sidebar
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <Link
      href="/notifications"
      className="relative flex items-center justify-center w-8 h-8 rounded-lg hover:bg-[#ebe8e3] transition-colors"
      aria-label={`Notifications${count > 0 ? ` (${count} unread)` : ""}`}
    >
      <Bell className="w-4 h-4 text-[#484852]" />
      {count > 0 && (
        <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-0.5 bg-[#b93232] text-white text-[9px] font-bold rounded-full flex items-center justify-center leading-none">
          {count > 9 ? "9+" : count}
        </span>
      )}
    </Link>
  );
}
