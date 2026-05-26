"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

/** Renders as a sidebar nav-item row — drop it inside a nav-group. */
export function NotificationBell() {
  const [count, setCount] = useState(0);
  const pathname = usePathname();
  const isActive = pathname === "/notifications";

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
      className={`nav-item${isActive ? " active" : ""}`}
    >
      {/* Bell icon — matches the SVG style of all other nav icons */}
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>

      <span style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
        Notifications
        {count > 0 && (
          <span
            style={{
              minWidth: "18px",
              height: "18px",
              padding: "0 4px",
              background: "#b93232",
              color: "#fff",
              fontSize: "9px",
              fontWeight: 700,
              borderRadius: "9px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              lineHeight: 1,
            }}
          >
            {count > 9 ? "9+" : count}
          </span>
        )}
      </span>
    </Link>
  );
}
