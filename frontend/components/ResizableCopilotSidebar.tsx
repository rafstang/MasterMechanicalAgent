"use client";

import { useCallback, useEffect, useState, type ComponentProps, type ReactNode } from "react";
import { CopilotSidebar } from "@copilotkit/react-ui";
import type { AttachmentUploadError } from "@copilotkit/shared";
import {
  ATTACHMENT_ACCEPT,
  ATTACHMENT_MAX_SIZE,
  attachmentUploadErrorMessage,
  uploadAttachment,
} from "../lib/attachments";
import { useResizableSidebarWidth } from "../hooks/useResizableSidebarWidth";

type CopilotSidebarProps = ComponentProps<typeof CopilotSidebar>;

export type ResizableCopilotSidebarProps = Omit<CopilotSidebarProps, "width"> & {
  children: ReactNode;
};

function readShowResizeHint(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return !localStorage.getItem("mm-resize-hint-dismissed");
  } catch {
    return true;
  }
}

export function ResizableCopilotSidebar({ children, ...sidebarProps }: ResizableCopilotSidebarProps) {
  const { width, isDragging, startDrag, resetWidth, nudgeWidth, keyboardStep } =
    useResizableSidebarWidth();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showResizeHint, setShowResizeHint] = useState(readShowResizeHint);

  const dismissResizeHint = useCallback(() => {
    setShowResizeHint(false);
    try {
      localStorage.setItem("mm-resize-hint-dismissed", "1");
    } catch {
      /* ignore */
    }
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    try {
      const result = await uploadAttachment(file);
      setUploadError(null);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed.";
      setUploadError(message);
      throw error;
    }
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--mm-sidebar-width", `${Math.round(width)}px`);
  }, [width]);

  const handleUploadFailed = useCallback((error: AttachmentUploadError) => {
    setUploadError(error.message || attachmentUploadErrorMessage(error.reason));
  }, []);

  const isMobile =
    typeof window !== "undefined" ? window.matchMedia("(max-width: 767px)").matches : false;

  return (
    <>
      <CopilotSidebar
        {...sidebarProps}
        attachments={{
          enabled: true,
          accept: ATTACHMENT_ACCEPT,
          maxSize: ATTACHMENT_MAX_SIZE,
          onUpload: handleUpload,
          onUploadFailed: handleUploadFailed,
        }}
      >
        {children}
      </CopilotSidebar>

      {!isMobile ? (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize chat panel"
          aria-valuenow={Math.round(width)}
          aria-valuemin={320}
          tabIndex={0}
          onPointerDown={(event) => {
            if (event.button !== 0) return;
            event.preventDefault();
            startDrag(event.clientX);
          }}
          onDoubleClick={resetWidth}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") {
              event.preventDefault();
              nudgeWidth(keyboardStep);
            } else if (event.key === "ArrowRight") {
              event.preventDefault();
              nudgeWidth(-keyboardStep);
            } else if (event.key === "Home") {
              event.preventDefault();
              resetWidth();
            }
          }}
          className={`fixed top-0 z-[10001] h-svh w-1 cursor-col-resize touch-none bg-transparent transition-colors hover:bg-emerald-500/30 focus:bg-emerald-500/40 focus:outline-none ${
            isDragging ? "bg-emerald-500/40" : ""
          }`}
          style={{ right: width - 2 }}
        />
      ) : null}

      {showResizeHint && !isMobile ? (
        <div
          className="fixed bottom-20 z-[10002] max-w-xs rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-600 shadow-lg"
          style={{ right: width + 12 }}
        >
          Drag the panel edge to resize. Double-click to reset.
          <button
            type="button"
            onClick={dismissResizeHint}
            className="ml-2 font-medium text-zinc-900 underline"
          >
            Got it
          </button>
        </div>
      ) : null}

      {uploadError ? (
        <div
          role="alert"
          className="fixed bottom-24 left-4 z-[10002] max-w-sm rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 shadow"
        >
          {uploadError}
          <button
            type="button"
            onClick={() => setUploadError(null)}
            className="ml-2 font-medium underline"
          >
            Dismiss
          </button>
        </div>
      ) : null}
    </>
  );
}
