"use client";

export type NodeStatus = "idle" | "running" | "done" | "error";

export interface PipelineNode {
  id: string;
  label: string;
  sublabel: string;
  status: NodeStatus;
  /** e.g. "1m 42s" — shown when status is done or error */
  duration?: string;
}

const STATUS_COLOR: Record<NodeStatus, string> = {
  idle:    "var(--ink-muted)",
  running: "var(--blue)",
  done:    "var(--green)",
  error:   "var(--red)",
};

const STATUS_BG: Record<NodeStatus, string> = {
  idle:    "var(--paper-warm)",
  running: "var(--blue-pale)",
  done:    "rgba(36,122,82,0.08)",
  error:   "rgba(185,50,50,0.08)",
};

const STATUS_LABEL: Record<NodeStatus, string> = {
  idle:    "idle",
  running: "running",
  done:    "done",
  error:   "error",
};

interface ConnectorProps {
  /** The node on the left side of this connector */
  leftStatus: NodeStatus;
}

/** Animated connector arrow between two nodes */
function Connector({ leftStatus }: ConnectorProps) {
  const isActive = leftStatus === "running";
  return (
    <div className="flex items-center shrink-0 px-1" style={{ width: 52 }}>
      <div className="relative flex-1 flex items-center" style={{ height: 2 }}>
        {/* Base line */}
        <div
          className="absolute inset-0 rounded"
          style={{ background: isActive ? "var(--blue)" : "var(--border)", opacity: isActive ? 0.4 : 1 }}
        />
        {/* Animated travelling dot */}
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
      <div
        className="text-[10px] ml-0.5 shrink-0"
        style={{ color: isActive ? "var(--blue)" : "var(--border)" }}
      >
        ▶
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

interface Props {
  nodes: PipelineNode[];
}

export default function PipelineView({ nodes }: Props) {
  return (
    <div className="flex items-center overflow-x-auto py-6 px-2">
      {nodes.map((node, i) => (
        <div key={node.id} className="flex items-center shrink-0">
          {/* Node card */}
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
            {/* Status indicator */}
            <div className="flex justify-center mb-2.5">
              {node.status === "running" ? (
                /* Spinning ring for running */
                <div
                  className="w-3 h-3 rounded-full border-2"
                  style={{
                    borderColor: `${STATUS_COLOR[node.status]}30`,
                    borderTopColor: STATUS_COLOR[node.status],
                    animation: "spin-slow 0.9s linear infinite",
                  }}
                />
              ) : (
                /* Static dot for idle / done / error */
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
            <div className="text-sm font-semibold" style={{ color: "var(--ink)" }}>{node.label}</div>

            {/* Sub-label */}
            <div
              className="text-xs mt-0.5"
              style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
            >
              {node.sublabel}
            </div>

            {/* Status + optional duration */}
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

          {/* Connector arrow */}
          {i < nodes.length - 1 && <Connector leftStatus={node.status} />}
        </div>
      ))}
    </div>
  );
}
