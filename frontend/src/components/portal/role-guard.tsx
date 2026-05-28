"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchUser } from "@/lib/auth";

/**
 * Client-side role guard. Call in layout.tsx to enforce role boundaries.
 * Security is enforced at the API layer; this just prevents UI confusion.
 */
export function usePortalGuard() {
  const router = useRouter();
  useEffect(() => {
    fetchUser().then((user) => {
      if (!user) { router.replace("/login"); return; }
      if (user.role !== "customer_admin") router.replace("/");
    });
  }, [router]);
}

export function useAdminGuard() {
  const router = useRouter();
  useEffect(() => {
    fetchUser().then((user) => {
      if (!user) { router.replace("/login"); return; }
      if (user.role === "customer_admin") router.replace("/dashboard");
    });
  }, [router]);
}
