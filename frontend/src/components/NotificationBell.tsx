"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Notification } from "@/lib/types";

const POLL_INTERVAL_MS = 30_000;

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const load = async () => {
    try {
      const data = await api<Notification[]>("/api/notifications");
      setNotifications(data);
    } catch {
      // silently skip — bell should never break the sidebar
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  // Close panel when clicking outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const dismiss = async (id: string) => {
    try {
      await api(`/api/notifications/${id}/read`, { method: "PATCH" });
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    } catch {
      // optimistic — reload on next poll
    }
  };

  const dismissAll = async () => {
    try {
      await api("/api/notifications/read-all", { method: "POST" });
      setNotifications([]);
      setOpen(false);
    } catch {
      // reload on next poll
    }
  };

  const unread = notifications.length;

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex items-center justify-center w-8 h-8 rounded-lg hover:bg-[#ebe8e3] transition-colors"
        aria-label={`Notifications${unread > 0 ? ` (${unread} unread)` : ""}`}
      >
        <Bell className="w-4 h-4 text-[#484852]" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-0.5 bg-[#b93232] text-white text-[9px] font-bold rounded-full flex items-center justify-center leading-none">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute bottom-10 left-0 w-[320px] bg-white border border-[#cfccc8] rounded-xl shadow-[0_8px_24px_rgba(0,0,0,0.12)] z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#ebe8e3] bg-[#f9f7f4]">
            <span className="text-[12px] font-bold text-[#1e1e24] uppercase tracking-widest">
              Notifications
            </span>
            {unread > 0 && (
              <button
                onClick={dismissAll}
                className="text-[11px] text-[#888894] hover:text-[#1e4d92] transition-colors font-medium"
              >
                Dismiss all
              </button>
            )}
          </div>

          {/* List */}
          {notifications.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <Bell className="w-6 h-6 text-[#cfccc8] mx-auto mb-2" />
              <p className="text-[12px] text-[#888894]">All clear — no alerts</p>
            </div>
          ) : (
            <ul className="max-h-[360px] overflow-y-auto divide-y divide-[#f2f0ed]">
              {notifications.map((n) => (
                <li
                  key={n.id}
                  className={`px-4 py-3 flex gap-3 ${
                    n.severity === "error"
                      ? "border-l-[3px] border-l-[#b93232]"
                      : "border-l-[3px] border-l-[#c17c00]"
                  }`}
                >
                  {/* Severity dot */}
                  <div className="pt-0.5 shrink-0">
                    <div
                      className={`w-2 h-2 rounded-full mt-1 ${
                        n.severity === "error" ? "bg-[#b93232]" : "bg-[#c17c00]"
                      }`}
                    />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-semibold text-[#1e1e24] leading-snug">
                      {n.title}
                    </div>
                    <div className="text-[11px] text-[#888894] mt-0.5 whitespace-pre-line leading-relaxed">
                      {n.body}
                    </div>
                    <div className="flex items-center gap-3 mt-1.5">
                      <span className="text-[10px] text-[#b4b4bc]">
                        {timeAgo(n.created_at)}
                      </span>
                      {n.link && (
                        <Link
                          href={n.link}
                          onClick={() => setOpen(false)}
                          className="text-[10px] font-semibold text-[#1e4d92] hover:underline"
                        >
                          View details →
                        </Link>
                      )}
                    </div>
                  </div>

                  {/* Dismiss */}
                  <button
                    onClick={() => dismiss(n.id)}
                    className="shrink-0 text-[#cfccc8] hover:text-[#484852] transition-colors mt-0.5"
                    aria-label="Dismiss"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
