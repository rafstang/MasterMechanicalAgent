"use client";

import { CopilotDevConsole, useChatContext } from "@copilotkit/react-ui";
import type { HeaderProps } from "@copilotkit/react-ui";
import { AgentRunStatus } from "./AgentRunStatus";

/**
 * Drop-in replacement for CopilotKit’s default sidebar header, with run status below the title row.
 */
export function SidebarHeaderWithStatus({}: HeaderProps) {
  const { setOpen, icons, labels } = useChatContext();

  return (
    <>
      <div className="copilotKitHeader">
        <div>{labels.title}</div>
        <div className="copilotKitHeaderControls">
          <CopilotDevConsole />
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close"
            className="copilotKitHeaderCloseButton"
          >
            {icons.headerCloseIcon}
          </button>
        </div>
      </div>
      <AgentRunStatus variant="sidebar" />
    </>
  );
}
