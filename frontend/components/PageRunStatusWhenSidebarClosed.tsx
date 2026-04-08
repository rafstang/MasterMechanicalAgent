"use client";

import { useChatContext } from "@copilotkit/react-ui";
import { AgentRunStatus } from "./AgentRunStatus";

/**
 * Shows the same run-status strip as the sidebar header, but on the main page when the chat panel is closed.
 * Avoids duplicate subscriptions: only one `AgentRunStatus` mounts at a time.
 */
export function PageRunStatusWhenSidebarClosed() {
  const { open } = useChatContext();
  if (open) return null;
  return <AgentRunStatus variant="page" />;
}
