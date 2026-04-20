"use client";

import React from "react";

export type NodeStatus = "idle" | "running" | "done" | "error";
export type NodeIcon = "supplier" | "fetch" | "normalize" | "store" | "publish";

const STATUS_COLOR: Record<NodeStatus, string> = {
  idle: "var(--ink-faint)",
  running: "var(--blue)",
  done: "var(--green)",
  error: "var(--red)",
};

const STATUS_BG: Record<NodeStatus, string> = {
  idle: "var(--vellum)",
  running: "var(--blue-pale)",
  done: "var(--green-pale)",
  error: "var(--red-pale)",
};

const STATUS_LABEL: Record<NodeStatus, string> = {
  idle: "idle",
  running: "running",
  done: "done",
  error: "error",
};

// ─── SVG icons matching Blueprint theme ──────────────────────────────────────

function IconSupplier({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="3" width="15" height="13" rx="1"/>
      <path d="M16 8h4l3 5v3h-7V8z"/>
      <circle cx="5.5" cy="18.5" r="2.5"/>
      <circle cx="18.5" cy="18.5" r="2.5"/>
    </svg>
  );
}

function IconFetch({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  );
}

function IconNormalize({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
    </svg>
  );
}

function IconStore({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/>
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  );
}

function IconPublish({ color }: { color: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13"/>
      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>
  );
}

function NodeIconComponent({ icon, status }: { icon?: NodeIcon; status: NodeStatus }) {
  const color = STATUS_COLOR[status];
  switch (icon) {
    case "supplier":  return <IconSupplier color={color} />;
    case "fetch":     return <IconFetch color={color} />;
    case "normalize": return <IconNormalize color={color} />;
    case "store":     return <IconStore color={color} />;
    case "publish":   return <IconPublish color={color} />;
    default:          return null;
  }
}

// ─── Connector ────────────────────────────────────────────────────────────────

interface ConnectorProps {
  leftStatus: NodeStatus;
}

function Connector({ leftStatus }: ConnectorProps) {
  const isActive = leftStatus === "running";
  return (
    <div className="flex items-center shrink-0 px-1" style={{ width: 52 }}>
      <div className="relative flex-1 flex items-center" style={{ height: 2 }}>
        <div
          className="absolute inset-0 rounded"
          style={{ background: isActive ? "var(--blue)" : "var(--border)", opacity: isActive ? 0.4 : 1 }}
        />
        {isActive && (
          <div
            className="absolute w-2 h-2 rounded-full"
            style={{
              background: "var(--blue)",
              top: "50%",
              transform: "translateY(-50%)",
              animation: "travel 1.2s linear infinite",
            }}
          />
        )}
      </div>
      <style>{`
        @keyframes travel {
          0%   { left: 0%; }
          100% { left: 100%; }
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.4; transform: scale(1.5); }
        }
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// ─── PipelineView ─────────────────────────────────────────────────────────────

export interface PipelineNode {
  id: string;
  label: string;
  sublabel: string;
  status: NodeStatus;
  icon?: NodeIcon;
  duration?: string;
}

interface Props {
  nodes: PipelineNode[];
}

export default function PipelineView({ nodes }: Props) {
  return (
    <div className="flex items-center overflow-x-auto py-6 px-2 justify-center">
      {nodes.map((node, i) => (
        <div key={node.id} className="flex items-center shrink-0">
          <div
            className="rounded-xl border px-5 py-4 min-w-[148px] text-center transition-all duration-300"
            style={{
              borderColor: STATUS_COLOR[node.status],
              background: STATUS_BG[node.status],
              boxShadow:
                node.status === "running"
                  ? `0 0 16px ${STATUS_COLOR[node.status]}30`
                  : node.status === "error"
                  ? `0 0 8px ${STATUS_COLOR[node.status]}20`
                  : "none",
            }}
          >
            {/* Icon */}
            {node.icon && (
              <div className="flex justify-center mb-3">
                <NodeIconComponent icon={node.icon} status={node.status} />
              </div>
            )}

            {/* Status indicator dot / spinner */}
            <div className="flex justify-center mb-2.5">
              {node.status === "running" ? (
                <div
                  className="w-3 h-3 rounded-full border-2"
                  style={{
                    borderColor: `${STATUS_COLOR[node.status]}30`,
                    borderTopColor: STATUS_COLOR[node.status],
                    animation: "spin-slow 0.9s linear infinite",
                  }}
                />
              ) : (
                <span
                  className="w-2.5 h-2.5 rounded-full inline-block"
                  style={{
                    background: STATUS_COLOR[node.status],
                    animation: node.status === "error" ? "pulse-dot 2s ease-in-out infinite" : "none",
                  }}
                />
              )}
            </div>

            {/* Label */}
            <div className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
              {node.label}
            </div>

            {/* Sub-label */}
            <div
              className="text-xs mt-0.5"
              style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
            >
              {node.sublabel}
            </div>

            {/* Status badge + duration */}
            <div className="mt-2 flex items-center justify-center gap-1.5">
              <span
                className="text-xs font-semibold"
                style={{ color: STATUS_COLOR[node.status], fontFamily: "var(--font-mono)" }}
              >
                {STATUS_LABEL[node.status]}
              </span>
              {node.duration && (node.status === "done" || node.status === "error") && (
                <span
                  className="text-xs px-1.5 py-px rounded"
                  style={{
                    background: "var(--paper-warm)",
                    color: "var(--ink-muted)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {node.duration}
                </span>
              )}
            </div>
          </div>

          {i < nodes.length - 1 && <Connector leftStatus={node.status} />}
        </div>
      ))}
    </div>
  );
}
