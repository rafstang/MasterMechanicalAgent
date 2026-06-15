"use client";

import type { WorkspaceDocumentContent } from "./WorkspaceContext";

export type DocumentPreviewProps = {
  document: WorkspaceDocumentContent;
};

export function DocumentPreview({ document }: DocumentPreviewProps) {
  const isPdf = document.mimeType === "application/pdf" || document.url.startsWith("data:application/pdf");
  const isText =
    document.mimeType.startsWith("text/") ||
    document.mimeType === "application/csv" ||
    document.mimeType === "application/json";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-zinc-200 bg-white px-4 py-3">
        <h2 className="text-base font-semibold text-zinc-900">{document.title}</h2>
        {document.filename ? (
          <p className="mt-1 text-sm text-zinc-500">{document.filename}</p>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-auto bg-zinc-100 p-4">
        {isPdf ? (
          <iframe
            src={document.url}
            title={document.title}
            className="h-full min-h-[480px] w-full rounded-lg border border-zinc-200 bg-white"
          />
        ) : isText ? (
          <iframe
            src={document.url}
            title={document.title}
            className="h-full min-h-[320px] w-full rounded-lg border border-zinc-200 bg-white"
          />
        ) : (
          <div className="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-600">
            Preview is not available for this file type. Ask the assistant to summarize its contents.
          </div>
        )}
      </div>
    </div>
  );
}
