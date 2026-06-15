"use client";

import { EventType } from "@ag-ui/client";
import { useAgent } from "@copilotkit/react-core/v2";
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

const AGENT_ID = "master_mechanical_agent";

type RunStatusPayload = {
  phase?: string;
  active_tool?: string | null;
  detail?: string | null;
};

function readRunStatus(state: unknown): RunStatusPayload | null {
  if (!state || typeof state !== "object") return null;
  const root = state as Record<string, unknown>;
  const rs = root.run_status;
  if (!rs || typeof rs !== "object") return null;
  const r = rs as Record<string, unknown>;
  return {
    phase: typeof r.phase === "string" ? r.phase : undefined,
    active_tool: typeof r.active_tool === "string" ? r.active_tool : r.active_tool === null ? null : undefined,
    detail: typeof r.detail === "string" ? r.detail : undefined,
  };
}

function humanizeToolName(name: string): string {
  const labels: Record<string, string> = {
    load_artifacts: "loading attachments",
    summarize_spreadsheet: "parsing spreadsheet",
    execute_sql: "querying BigQuery",
    display_in_workspace: "opening workspace view",
  };
  return labels[name] ?? name.replace(/_/g, " ");
}

function labelFromRunStatus(rs: RunStatusPayload): string | null {
  const tool = rs.active_tool ? humanizeToolName(rs.active_tool) : null;
  switch (rs.phase) {
    case "thinking":
      return "Thinking…";
    case "tool_calling":
      return tool ? `Calling ${tool}…` : "Calling a tool…";
    case "summarizing":
      if (rs.detail?.startsWith("Completed")) return "Summarizing results…";
      return rs.detail ?? "Preparing answer…";
    case "done":
      return null;
    default:
      return rs.detail ?? null;
  }
}

function applyRunStatusToLine(
  setLine: Dispatch<SetStateAction<string | null>>,
  rs: RunStatusPayload | null
): boolean {
  if (!rs) return false;
  if (rs.phase === "done") {
    setLine(null);
    return true;
  }
  const text = labelFromRunStatus(rs);
  if (text) {
    setLine(text);
    return true;
  }
  return false;
}

function labelFromEvent(event: { type: string } & Record<string, unknown>): string | null {
  switch (event.type) {
    case EventType.RUN_STARTED:
      return "Working…";
    case EventType.TOOL_CALL_START: {
      const name = typeof event.toolCallName === "string" ? event.toolCallName : "";
      return name ? `Calling ${humanizeToolName(name)}…` : "Calling a tool…";
    }
    case EventType.TOOL_CALL_ARGS:
      return "Receiving tool arguments…";
    case EventType.TOOL_CALL_END:
      return "Running tool…";
    case EventType.TOOL_CALL_RESULT:
      return "Processing tool result…";
    case EventType.TEXT_MESSAGE_CONTENT:
    case EventType.TEXT_MESSAGE_CHUNK:
      return "Writing response…";
    case EventType.REASONING_START:
    case EventType.REASONING_MESSAGE_START:
    case EventType.REASONING_MESSAGE_CONTENT:
    case EventType.REASONING_MESSAGE_CHUNK:
      return "Reasoning…";
    case EventType.RUN_ERROR:
      return "Run error";
    default:
      return null;
  }
}

export type AgentRunStatusVariant = "page" | "sidebar";

export type AgentRunStatusProps = {
  /** `sidebar` uses tighter spacing to sit under the CopilotKit header. */
  variant?: AgentRunStatusVariant;
};

/**
 * Shows what the AG-UI agent is doing (tools, streaming text, backend run_status).
 * Must render under <CopilotKit> so useAgent resolves the HttpAgent instance.
 */
export function AgentRunStatus({ variant = "page" }: AgentRunStatusProps) {
  const { agent } = useAgent({ agentId: AGENT_ID, updates: [] });

  const [line, setLine] = useState<string | null>(null);

  useEffect(() => {
    const applyState = (state: unknown) => {
      applyRunStatusToLine(setLine, readRunStatus(state));
    };

    applyState(agent.state);

    const { unsubscribe } = agent.subscribe({
      onEvent: ({ event, state }) => {
        const fromEvent = labelFromEvent(event as { type: string } & Record<string, unknown>);
        const rs = readRunStatus(state);
        if (applyRunStatusToLine(setLine, rs)) return;
        if (fromEvent) setLine(fromEvent);
      },
      onStateChanged: ({ state }) => {
        applyState(state);
      },
      onRunStartedEvent: ({ state }) => {
        if (!applyRunStatusToLine(setLine, readRunStatus(state))) {
          setLine((prev) => prev ?? "Working…");
        }
      },
      onRunFinishedEvent: ({ state }) => {
        if (!applyRunStatusToLine(setLine, readRunStatus(state))) {
          setLine(null);
        }
      },
      onRunErrorEvent: () => {
        setLine("Something went wrong");
      },
      onRunFinalized: () => {
        setLine(null);
      },
      onRunFailed: () => {
        setLine("Something went wrong");
      },
    });

    return () => unsubscribe();
  }, [agent]);

  if (!agent.isRunning && !line) {
    return null;
  }

  const shellClass =
    variant === "sidebar"
      ? "flex items-center gap-1.5 border-b border-zinc-200/90 bg-zinc-100/90 px-3 py-1.5 text-xs text-zinc-600"
      : "flex items-center gap-2 border-b border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-700";

  const dotClass =
    variant === "sidebar"
      ? "inline-block size-1.5 shrink-0 animate-pulse rounded-full bg-emerald-500"
      : "inline-block size-2 shrink-0 animate-pulse rounded-full bg-emerald-500";

  return (
    <div className={shellClass} role="status" aria-live="polite">
      <span className={dotClass} aria-hidden />
      <span className="min-w-0 truncate">{line ?? "Working…"}</span>
    </div>
  );
}
