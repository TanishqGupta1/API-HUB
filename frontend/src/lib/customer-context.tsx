"use client";

/**
 * Phase 6 — global "active customer" context.
 *
 * Pages that act on a specific customer (Products page add-to-catalog,
 * future bulk actions, dashboard widgets) read the active customer from
 * this context. Persists to localStorage so reloads keep the selection.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import { toast } from "sonner";

const ID_KEY = "apiHub.selectedCustomerId";
const NAME_KEY = "apiHub.selectedCustomerName";

type Ctx = {
  selectedCustomerId: string | null;
  selectedCustomerName: string | null;
  setSelectedCustomer: (id: string | null, name: string | null) => void;
  bulkAdd: (productIds: string[]) => Promise<{ success: boolean; count: number }>;
  /** Cleared after first read after a SSR-hydration cycle. */
  hydrated: boolean;
};

const CustomerContext = createContext<Ctx | null>(null);

export function CustomerProvider({ children }: { children: ReactNode }) {
  const [selectedCustomerId, setIdState] = useState<string | null>(null);
  const [selectedCustomerName, setNameState] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  // Hydrate from localStorage exactly once on mount (client-only).
  useEffect(() => {
    try {
      const storedId = window.localStorage.getItem(ID_KEY);
      const storedName = window.localStorage.getItem(NAME_KEY);
      if (storedId) setIdState(storedId);
      if (storedName) setNameState(storedName);
    } catch {
      // localStorage may be blocked in some contexts — fail silent.
    }
    setHydrated(true);
  }, []);

  const setSelectedCustomer = useCallback((id: string | null, name: string | null) => {
    setIdState(id);
    setNameState(name);
    try {
      if (id) {
        window.localStorage.setItem(ID_KEY, id);
        if (name) window.localStorage.setItem(NAME_KEY, name);
      } else {
        window.localStorage.removeItem(ID_KEY);
        window.localStorage.removeItem(NAME_KEY);
      }
    } catch {
      // ignore
    }
  }, []);

  const bulkAdd = useCallback(async (productIds: string[]) => {
    if (!selectedCustomerId || productIds.length === 0) return { success: false, count: 0 };
    try {
      const res = await api<{ count: number }>(`/api/customers/${selectedCustomerId}/selections/bulk`, {
        method: "POST",
        body: JSON.stringify({ product_ids: productIds })
      });
      toast.success(`Successfully added ${res.count} products to ${selectedCustomerName}`);
      return { success: true, count: res.count };
    } catch (err) {
      toast.error("Failed to perform bulk add");
      return { success: false, count: 0 };
    }
  }, [selectedCustomerId, selectedCustomerName]);

  return (
    <CustomerContext.Provider
      value={{ selectedCustomerId, selectedCustomerName, setSelectedCustomer, bulkAdd, hydrated }}
    >
      {children}
    </CustomerContext.Provider>
  );
}

export function useSelectedCustomer(): Ctx {
  const ctx = useContext(CustomerContext);
  if (ctx == null) {
    throw new Error(
      "useSelectedCustomer must be used inside <CustomerProvider>",
    );
  }
  return ctx;
}
