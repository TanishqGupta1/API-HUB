import { describe, expect, it } from "vitest";
import {
  PUSH_STATUS_CONFIG,
  getStatusConfig,
  isInFlight,
  isTerminal,
} from "@/lib/push-status";

describe("push-status central map", () => {
  it("covers the full Rev 3 status vocabulary", () => {
    // Spec push pipeline statuses
    expect(PUSH_STATUS_CONFIG.accepted).toBeDefined();
    expect(PUSH_STATUS_CONFIG.processing).toBeDefined();
    expect(PUSH_STATUS_CONFIG.pushed).toBeDefined();
    expect(PUSH_STATUS_CONFIG.failed).toBeDefined();
    expect(PUSH_STATUS_CONFIG.partial_failure).toBeDefined();
    expect(PUSH_STATUS_CONFIG.rejected).toBeDefined();
    expect(PUSH_STATUS_CONFIG.dry_run_pushed).toBeDefined();
    // Customer-catalog overlay statuses
    expect(PUSH_STATUS_CONFIG.selected).toBeDefined();
    expect(PUSH_STATUS_CONFIG.stale).toBeDefined();
    // Legacy fallbacks
    expect(PUSH_STATUS_CONFIG.pending).toBeDefined();
    expect(PUSH_STATUS_CONFIG.skipped).toBeDefined();
  });

  it("every status has a non-empty label, hex color, and category", () => {
    for (const [key, cfg] of Object.entries(PUSH_STATUS_CONFIG)) {
      expect(cfg.label, `${key} label`).toMatch(/\S/);
      expect(cfg.color, `${key} color`).toMatch(/^#/);
      expect(cfg.category, `${key} category`).toMatch(
        /^(pre|in_flight|success|warning|error|neutral)$/,
      );
    }
  });
});

describe("getStatusConfig", () => {
  it("returns the canonical config for a known status", () => {
    expect(getStatusConfig("pushed").label).toBe("Pushed");
    expect(getStatusConfig("accepted").label).toBe("Accepted");
  });

  it("returns a labeled fallback for an unknown status", () => {
    const cfg = getStatusConfig("mystery_state");
    expect(cfg.label).toBe("mystery_state");
    expect(cfg.color).toBeTruthy();
  });

  it("handles null and undefined input", () => {
    expect(getStatusConfig(null).label).toBe("Unknown");
    expect(getStatusConfig(undefined).label).toBe("Unknown");
  });
});

describe("isInFlight", () => {
  it("returns true for queued/running states", () => {
    expect(isInFlight("accepted")).toBe(true);
    expect(isInFlight("processing")).toBe(true);
    expect(isInFlight("pending")).toBe(true);
  });

  it("returns false for terminal and pre-push states", () => {
    expect(isInFlight("pushed")).toBe(false);
    expect(isInFlight("failed")).toBe(false);
    expect(isInFlight("selected")).toBe(false);
    expect(isInFlight(null)).toBe(false);
  });
});

describe("isTerminal", () => {
  it("returns true for states that won't change without further action", () => {
    expect(isTerminal("pushed")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
    expect(isTerminal("partial_failure")).toBe(true);
    expect(isTerminal("rejected")).toBe(true);
    expect(isTerminal("dry_run_pushed")).toBe(true);
  });

  it("returns false for in-flight and pre-push states", () => {
    expect(isTerminal("accepted")).toBe(false);
    expect(isTerminal("processing")).toBe(false);
    expect(isTerminal("selected")).toBe(false);
    expect(isTerminal("stale")).toBe(false);
  });
});
