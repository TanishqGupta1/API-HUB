"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, AlertTriangle, Bell, CheckCircle2, ExternalLink, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { toast } from "sonner";
import type { Notification } from "@/lib/types";

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const TYPE_LABELS: Record<string, string> = {
  push_failed: "Push Failed",
  sync_failed: "Sync Failed",
  scheduler_down: "Scheduler Down",
};

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRead, setShowRead] = useState(false);

  const load = async (includeRead = showRead) => {
    setLoading(true);
    try {
      const data = await api<Notification[]>(
        `/api/notifications${includeRead ? "?include_read=true" : ""}`
      );
      setNotifications(data);
    } catch (e) {
      log.warn("Failed to load notifications", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(showRead);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showRead]);

  const dismiss = async (id: string) => {
    try {
      await api(`/api/notifications/${id}/read`, { method: "PATCH" });
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    } catch {
      toast.error("Failed to dismiss notification");
    }
  };

  const dismissAll = async () => {
    try {
      await api("/api/notifications/read-all", { method: "POST" });
      if (showRead) {
        await load(true);
      } else {
        setNotifications([]);
      }
      toast.success("All notifications dismissed");
    } catch {
      toast.error("Failed to dismiss notifications");
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <header className="flex items-end justify-between pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Notifications
          </div>
          <p className="text-[13px] text-[#888894] mt-2">
            {unreadCount > 0
              ? `${unreadCount} unread alert${unreadCount > 1 ? "s" : ""}`
              : "No unread alerts"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowRead((v) => !v)}
            className="text-[11px] font-semibold text-[#888894] hover:text-[#1e1e24] transition-colors uppercase tracking-wide"
          >
            {showRead ? "Hide dismissed" : "Show all"}
          </button>
          <button
            onClick={async () => {
              try {
                await api("/api/notifications/demo", { method: "POST" });
                await load(showRead);
                toast.success("3 demo alerts created");
              } catch {
                toast.error("Failed to create demo alerts");
              }
            }}
            className="px-4 h-9 bg-white border-2 border-dashed border-[#888894] text-[#888894] rounded-full font-bold text-[11px] uppercase tracking-wide hover:border-[#1e1e24] hover:text-[#1e1e24] transition-colors"
          >
            Generate demo alerts
          </button>
          {unreadCount > 0 && (
            <button
              onClick={dismissAll}
              className="px-4 h-9 bg-white border-2 border-[#1e1e24] text-[#1e1e24] rounded-full font-bold text-[11px] uppercase tracking-wide hover:bg-[#f2f0ed] transition-colors"
            >
              Dismiss all
            </button>
          )}
        </div>
      </header>

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-28 bg-white rounded-2xl border border-[#cfccc8] animate-pulse"
            />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <div className="bg-white border-2 border-dashed border-[#cfccc8] rounded-2xl p-16 text-center">
          <Bell className="w-10 h-10 text-[#cfccc8] mx-auto mb-4" />
          <div className="text-[16px] font-bold text-[#1e1e24]">All clear</div>
          <p className="text-[13px] text-[#888894] mt-2">
            No alerts — push failures, sync errors, and scheduler issues will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => {
            const isError = n.severity === "error";
            return (
              <div
                key={n.id}
                className={`bg-white rounded-2xl border-2 px-6 py-5 flex gap-4 ${
                  n.is_read
                    ? "border-[#ebe8e3] opacity-60"
                    : isError
                    ? "border-[#b93232]"
                    : "border-[#c17c00]"
                }`}
              >
                {/* Icon */}
                <div className="shrink-0 mt-0.5">
                  {n.is_read ? (
                    <CheckCircle2 className="w-5 h-5 text-[#b4b4bc]" />
                  ) : isError ? (
                    <AlertCircle className="w-5 h-5 text-[#b93232]" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-[#c17c00]" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <span
                        className={`inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded mb-2 ${
                          n.is_read
                            ? "bg-[#f2f0ed] text-[#888894]"
                            : isError
                            ? "bg-[#fdf2f2] text-[#b93232]"
                            : "bg-[#fff7e0] text-[#c17c00]"
                        }`}
                      >
                        {TYPE_LABELS[n.type] ?? n.type}
                      </span>
                      <div className="text-[15px] font-bold text-[#1e1e24] leading-snug">
                        {n.title}
                      </div>
                    </div>
                    <span className="text-[11px] text-[#b4b4bc] shrink-0 mt-1">
                      {timeAgo(n.created_at)}
                    </span>
                  </div>

                  <pre className="text-[12px] text-[#484852] mt-2 whitespace-pre-wrap font-sans leading-relaxed">
                    {n.body}
                  </pre>

                  <div className="flex items-center gap-4 mt-3">
                    {n.link && n.link.startsWith("/") && (
                      <Link
                        href={n.link}
                        className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#1e4d92] hover:underline"
                      >
                        View details
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    )}
                    {!n.is_read && (
                      <button
                        onClick={() => dismiss(n.id)}
                        className="inline-flex items-center gap-1 text-[12px] text-[#888894] hover:text-[#1e1e24] transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                        Dismiss
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
