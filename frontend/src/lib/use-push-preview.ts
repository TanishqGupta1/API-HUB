/**
 * Integration Gateway (M0–M5) — push hooks.
 *
 * Replaces the old VPCE preview/execute pair with a single
 * `POST /api/integrations/v1/push-requests` (with `dry_run` flag) plus
 * a `GET /push-requests/{id}` poll.
 *
 * When `NEXT_PUBLIC_PHASE8_LIVE=true`, hooks call the real backend. Default
 * is mock mode, which serves fixtures so designers can demo every status
 * (queued/processing/pushed/partial_failure/dry_run_pushed/rejected) via
 * the `?demo=` URL flag.
 *
 * Exported hooks:
 *   - usePushDryRun(customerId, productId): hook that auto-runs a dry-run
 *     on mount to populate the preview panel (computed prices + plan).
 *   - usePushRequest(): imperative hook that sends a real or dry-run
 *     request to POST /push-requests.
 *   - usePushStatus(pushLogId): poll hook for the status detail page.
 *
 * Legacy names (`usePushPreview` / `usePushExecute`) re-exported as
 * thin aliases so existing imports keep compiling during the migration.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "./api";
import {
  FIXTURE_ERROR_PREFLIGHT_BLOCKER,
  FIXTURE_PREFLIGHT_BLOCKED,
  FIXTURE_PREFLIGHT_PASS,
  FIXTURE_PUSH_LOG_DRY_RUN_PUSHED,
  FIXTURE_PUSH_LOG_FAILED,
  FIXTURE_PUSH_LOG_PROCESSING,
  FIXTURE_PUSH_LOG_PUSHED,
  FIXTURE_PUSH_LOG_REJECTED,
  FIXTURE_PUSH_TERMINAL_DRY_RUN,
  FIXTURE_PUSH_TERMINAL_PUSHED,
  FIXTURE_OPS_PUSH_PAYLOAD,
} from "./push-fixtures";
import type {
  GatewayErrorEnvelope,
  OPSPushPayload,
  PreflightResult,
  PushAcceptedResponse,
  PushLog,
  PushRequestBody,
  PushRequestResponse,
  PushTerminalResponse,
} from "./types";

// ───────────────────────────────────────────────────────────────────────────
// Mode toggle
// ───────────────────────────────────────────────────────────────────────────

const LIVE_MODE =
  typeof process !== "undefined" &&
  process.env.NEXT_PUBLIC_PHASE8_LIVE === "true";

const ADMIN_PROXY_MODE =
  typeof process !== "undefined" &&
  process.env.NEXT_PUBLIC_PHASE8_ADMIN_PROXY === "true";

export const IS_MOCK_MODE = !LIVE_MODE;

const _UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function _isUuid(s: string | null | undefined): boolean {
  return !!s && _UUID_RE.test(s);
}

/** Endpoint switch — admin proxy uses JWT, gateway uses X-Orchestrator-Key.
 *  Admin-proxy lets the in-app admin UI push without the operator pasting a key. */
const PUSH_ENDPOINT = ADMIN_PROXY_MODE
  ? "/api/integrations/admin/push-requests"
  : "/api/integrations/v1/push-requests";

/** Status-poll URL — same shape, just JWT-auth vs orchestrator-key. */
const pushStatusUrl = (id: string) =>
  ADMIN_PROXY_MODE
    ? `/api/integrations/admin/push-requests/${id}`
    : `/api/integrations/v1/push-requests/${id}`;

/** `?demo=blocked` → preflight returns blockers in mock mode. */
function _demoFlag(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("demo");
}

function _delay(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}

// ───────────────────────────────────────────────────────────────────────────
// Idempotency-Key helper (caller chooses; we just want a unique string)
// ───────────────────────────────────────────────────────────────────────────

function _newIdempotencyKey(supplier_sku: string): string {
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "");
  const rand = Math.random().toString(36).slice(2, 8);
  return `ui-${supplier_sku}-${stamp}-${rand}`;
}

// ───────────────────────────────────────────────────────────────────────────
// usePushDryRun — auto-runs dry-run on mount; populates the preview panel
// ───────────────────────────────────────────────────────────────────────────

export interface UsePushDryRunResult {
  /** Dry-run preflight result (also returned inside the gateway 422 envelope). */
  preflight: PreflightResult | null;
  /** Dry-run plan & computed prices (returned from POST /push-requests with dry_run=true). */
  payload: OPSPushPayload | null;
  /** When preflight blocks the dry-run, the full error envelope. */
  error: GatewayErrorEnvelope | null;
  loading: boolean;
  refetch: () => void;
}

export function usePushDryRun(
  customerId: string | null,
  productId: string,
  supplierSlug?: string | null,
): UsePushDryRunResult {
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [payload, setPayload] = useState<OPSPushPayload | null>(null);
  const [error, setError] = useState<GatewayErrorEnvelope | null>(null);
  const [loading, setLoading] = useState(true);
  const [refetchCount, setRefetchCount] = useState(0);

  useEffect(() => {
    if (!customerId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      if (IS_MOCK_MODE || !_isUuid(customerId) || !_isUuid(productId)) {
        await _delay(400);
        if (cancelled) return;
        if (_demoFlag() === "blocked") {
          setPreflight(FIXTURE_PREFLIGHT_BLOCKED);
          setPayload(null);
          setError(FIXTURE_ERROR_PREFLIGHT_BLOCKER);
        } else {
          setPreflight(FIXTURE_PREFLIGHT_PASS);
          setPayload(FIXTURE_OPS_PUSH_PAYLOAD);
          setError(null);
        }
        setLoading(false);
        return;
      }

      try {
        // Live mode: dry-run POST to discover the plan + computed prices.
        const body: PushRequestBody = {
          target: { system: "ops", customer_id: customerId },
          source: { supplier_slug: supplierSlug ?? "sanmar" },
          product_ref: { product_id: productId },
          dry_run: true,
        };
        const resp = await api<PushRequestResponse>(
          PUSH_ENDPOINT,
          {
            method: "POST",
            headers: {
              "Idempotency-Key": _newIdempotencyKey("dryrun"),
              "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
          },
        );
        if (cancelled) return;
        if ("plan" in resp && resp.plan) {
          setPayload(resp.plan);
        }
        setPreflight(null);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        // Recover the PREFLIGHT_BLOCKER envelope that api() attaches as .envelope
        const raw = e instanceof ApiError ? e.envelope : undefined;
        const env: GatewayErrorEnvelope =
          raw != null && typeof raw === "object" && "code" in (raw as object)
            ? (raw as GatewayErrorEnvelope)
            : {
                status: "error",
                code: "PREFLIGHT_BLOCKER",
                message: e instanceof Error ? e.message : String(e),
                details: {},
                trace_id: null,
              };
        setError(env);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [customerId, productId, supplierSlug, refetchCount]);

  return {
    preflight,
    payload,
    error,
    loading,
    refetch: useCallback(() => setRefetchCount((n) => n + 1), []),
  };
}

// ───────────────────────────────────────────────────────────────────────────
// usePushRequest — imperative POST /push-requests
// ───────────────────────────────────────────────────────────────────────────

export interface PushRequestArgs {
  customerId: string;
  productId: string;
  supplierSlug: string;
  supplierSku: string;
  dryRun: boolean;
  /** Optional override for the mock-mode response (used by ?demo=). */
  mockMode?: "pushed" | "dry_run_pushed" | "partial_failure" | "queued";
  callback?: { url: string; secret?: string };
}

export interface UsePushRequestResult {
  push: (args: PushRequestArgs) => Promise<PushRequestResponse | null>;
  loading: boolean;
  error: GatewayErrorEnvelope | string | null;
}

export function usePushRequest(): UsePushRequestResult {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<GatewayErrorEnvelope | string | null>(null);

  const push = useCallback(
    async (args: PushRequestArgs): Promise<PushRequestResponse | null> => {
      setLoading(true);
      setError(null);
      try {
        if (IS_MOCK_MODE || !_isUuid(args.customerId) || !_isUuid(args.productId)) {
          await _delay(600);
          if (args.dryRun) return FIXTURE_PUSH_TERMINAL_DRY_RUN;
          switch (args.mockMode) {
            case "partial_failure":
              return {
                ...FIXTURE_PUSH_TERMINAL_PUSHED,
                push_log_id: FIXTURE_PUSH_LOG_FAILED.id,
                status: "partial_failure",
              };
            case "queued":
              return {
                push_log_id: FIXTURE_PUSH_LOG_PROCESSING.id,
                status: "queued",
                customer_id: args.customerId,
                supplier_slug: args.supplierSlug,
                supplier_sku: args.supplierSku,
                ops_product_id: null,
                dry_run: false,
                callback_status: args.callback ? "pending" : "not_requested",
                created_at: new Date().toISOString(),
                links: {
                  self: `/api/integrations/v1/push-requests/${FIXTURE_PUSH_LOG_PROCESSING.id}`,
                },
              } as PushAcceptedResponse;
            default:
              return FIXTURE_PUSH_TERMINAL_PUSHED;
          }
        }

        const body: PushRequestBody = {
          target: { system: "ops", customer_id: args.customerId },
          source: { supplier_slug: args.supplierSlug },
          product_ref: { product_id: args.productId },
          dry_run: args.dryRun,
          callback: args.callback,
        };
        const resp = await api<PushRequestResponse>(
          PUSH_ENDPOINT,
          {
            method: "POST",
            headers: {
              "Idempotency-Key": _newIdempotencyKey(args.supplierSku),
              "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
          },
        );
        return resp;
      } catch (e) {
        const env = (e as { envelope?: GatewayErrorEnvelope }).envelope;
        setError(env ?? String(e));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { push, loading, error };
}

// ───────────────────────────────────────────────────────────────────────────
// usePushStatus — poll GET /push-requests/{id} for the detail page
// ───────────────────────────────────────────────────────────────────────────

export interface UsePushStatusResult {
  log: PushLog | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function usePushStatus(pushLogId: string | null): UsePushStatusResult {
  const [log, setLog] = useState<PushLog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchCount, setRefetchCount] = useState(0);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!pushLogId) {
      setLoading(false);
      return;
    }
    const id = pushLogId; // narrow for the async closure
    let cancelled = false;
    setLoading(true);
    setError(null);

    async function load() {
      if (pollTimer.current) {
        clearTimeout(pollTimer.current);
        pollTimer.current = null;
      }
      try {
        if (IS_MOCK_MODE || !_isUuid(id)) {
          await _delay(350);
          if (cancelled) return;
          const demo = _demoFlag();
          let fixture: PushLog;
          if (demo === "pushed") fixture = FIXTURE_PUSH_LOG_PUSHED;
          else if (demo === "failed") fixture = FIXTURE_PUSH_LOG_FAILED;
          else if (demo === "rejected") fixture = FIXTURE_PUSH_LOG_REJECTED;
          else if (demo === "processing") fixture = FIXTURE_PUSH_LOG_PROCESSING;
          else fixture = FIXTURE_PUSH_LOG_DRY_RUN_PUSHED;
          setLog({ ...fixture, id });
          setLoading(false);
          return;
        }

        const raw = await api<PushLog & { push_log_id?: string }>(pushStatusUrl(id));
        if (cancelled) return;
        // Backend returns push_log_id as the primary key; normalise to `id`
        const fresh: PushLog = raw.id ? raw : { ...raw, id: raw.push_log_id ?? id };
        setLog(fresh);
        setLoading(false);

        // Poll while non-terminal
        const nonTerminal = ["queued", "processing"].includes(fresh.status);
        if (nonTerminal) {
          pollTimer.current = setTimeout(load, 2000);
        }
      } catch (e) {
        if (!cancelled) {
          setError(String(e));
          setLoading(false);
        }
      }
    }
    load();

    return () => {
      cancelled = true;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [pushLogId, refetchCount]);

  return {
    log,
    loading,
    error,
    refetch: useCallback(() => setRefetchCount((n) => n + 1), []),
  };
}

// ───────────────────────────────────────────────────────────────────────────
// Legacy aliases — keep old call sites compiling during migration
// ───────────────────────────────────────────────────────────────────────────

/** @deprecated Use `usePushDryRun` instead. */
export const usePushPreview = (
  customerId: string | null,
  productId: string,
) => {
  const { preflight, payload, error, loading, refetch } = usePushDryRun(
    customerId,
    productId,
  );
  return {
    data: payload && preflight
      ? { preflight, plan: payload.plan, computed_prices: payload.computed_prices, supplier_sku: payload.supplier_sku, preview_id: "mock", input_hash: payload.built_at, confirm_token: "" }
      : null,
    loading,
    error: error?.message ?? null,
    refetch,
  };
};

/** @deprecated Use `usePushRequest` instead. */
export const usePushExecute = () => {
  const { push, loading, error } = usePushRequest();
  return {
    execute: async (args: {
      customerId: string;
      productId: string;
      previewId: string;
      inputHash: string;
      dryRun: boolean;
      confirmToken?: string;
    }) => {
      const resp = await push({
        customerId: args.customerId,
        productId: args.productId,
        supplierSlug: "sanmar",
        supplierSku: "",
        dryRun: args.dryRun,
      });
      return resp ? { push_log_id: resp.push_log_id, status: resp.status } : null;
    },
    loading,
    error: typeof error === "string" ? error : error?.message ?? null,
  };
};
