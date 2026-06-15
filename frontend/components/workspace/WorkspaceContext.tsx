"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type WorkspaceTableContent = {
  type: "table";
  title: string;
  columns: string[];
  rows: string[][];
};

export type WorkspaceDocumentContent = {
  type: "document";
  title: string;
  mimeType: string;
  url: string;
  filename?: string;
};

export type WorkspaceContent = WorkspaceTableContent | WorkspaceDocumentContent | null;

type WorkspaceContextValue = {
  content: WorkspaceContent;
  setContent: (content: WorkspaceContent) => void;
  clearContent: () => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [content, setContentState] = useState<WorkspaceContent>(null);

  const setContent = useCallback((next: WorkspaceContent) => {
    setContentState(next);
  }, []);

  const clearContent = useCallback(() => {
    setContentState(null);
  }, []);

  const value = useMemo(
    () => ({ content, setContent, clearContent }),
    [content, setContent, clearContent]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  }
  return ctx;
}
