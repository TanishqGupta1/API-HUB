"use client";

import { useEffect, useState } from "react";

type NodeStatus = "idle" | "running" | "done" | "error";

interface PipelineNode {
  id: string;
  label: string;
  sublabel: string;
  status: NodeStatus;
}

const STATUS_COLOR: Record<NodeStatus, string> = {
  idle: "var(--ink-muted)",
  running: "var(--blueprint)",
  done: "var(--green)",
  error: "var(--red)",
};

const STATUS_BG: Record<NodeStatus, string> = {
  idle: "var(--paper-dark)",
  running: "var(--bp-pale)",
  done: "rgba(36,122,82,0.1)",
  error: "rgba(185,50,50,0.1)",
};

interface Props {
  nodes: PipelineNode[];
}

export default function PipelineView({ nodes }: Props) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto py-6 px-2">
      {nodes.map((node, i) => (
        <div key={node.id} className="flex items-center shrink-0">
          {/* Node card */}
          <div
            className="rounded-xl border px-5 py-4 min-w-[140px] text-center transition-all"
            style={{
              borderColor: STATUS_COLOR[node.status],
              background: STATUS_BG[node.status],
              boxShadow: node.status === "running" ? `0 0 12px ${STATUS_COLOR[node.status]}40` : "none",
            }}
          >
            {/* Pulse dot */}
            <div className="flex justify-center mb-2">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{
                  background: STATUS_COLOR[node.status],
                  animation: node.status === "running" ? "pulse 1.4s ease-in-out infinite" : "none",
                }}
              />
            </div>
            <div className="text-sm font-semibold" style={{ color: "var(--ink)" }}>{node.label}</div>
            <div className="text-xs mt-0.5" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
              {node.sublabel}
            </div>
            <div
              className="text-xs font-semibold mt-2"
              style={{ color: STATUS_COLOR[node.status], fontFamily: "var(--font-mono)" }}
            >
              {node.status}
            </div>
          </div>

          {/* Arrow connector */}
          {i < nodes.length - 1 && (
            <div className="flex items-center px-2" style={{ color: "var(--ink-muted)" }}>
              <div className="w-8 h-px" style={{ background: "var(--border)" }} />
              <div className="text-xs" style={{ color: "var(--ink-muted)" }}>▶</div>
            </div>
          )}
        </div>
      ))}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.4); }
        }
      `}</style>
    </div>
  );
}
