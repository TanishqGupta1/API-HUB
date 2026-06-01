"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { Notification } from "@/lib/types";

const POLL_INTERVAL_MS = 30_000;

/** Renders as a sidebar nav-item row — drop it inside a nav-group. */
export function NotificationBell() {
  const [count, setCount] = useState(0);
  const pathname = usePathname();
  const router = useRouter();
  const isActive = pathname === "/notifications";

  // Track which notification IDs have already been toasted so we never
  // duplicate a popup across poll ticks.
  const seenIds = useRef<Set<string>>(new Set());
  const initialized = useRef(false);

  const load = async () => {
    try {
      const notifications = await api<Notification[]>("/api/notifications");
      setCount(notifications.filter((n) => !n.is_read).length);

      if (!initialized.current) {
        // First load — seed seen set silently, no popups for existing alerts.
        notifications.forEach((n) => seenIds.current.add(n.id));
        initialized.current = true;
        return;
      }

      // Subsequent polls — toast anything we haven't seen yet.
      for (const n of notifications) {
        if (seenIds.current.has(n.id)) continue;
        seenIds.current.add(n.id);

        // Only follow internal paths — never navigate to absolute or javascript: URLs.
        const link = n.link && n.link.startsWith("/") ? n.link : null;
        const action = link
          ? { label: "View", onClick: () => router.push(link) }
          : undefined;
        const description = n.body.split("\n")[0];

        if (n.severity === "error") {
          toast.error(n.title, { description, action, duration: 8000 });
        } else {
          toast.warning(n.title, { description, action, duration: 8000 });
        }
      }
    } catch {
      // never break the sidebar
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Link
      href="/notifications"
      className={`nav-item${isActive ? " active" : ""}`}
    >
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
