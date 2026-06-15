"use client";

import { useFrontendTool } from "@copilotkit/react-core";
import { DataTableView } from "./DataTableView";
import { DocumentPreview } from "./DocumentPreview";
import { useWorkspace } from "./WorkspaceContext";
import { WelcomeCards } from "./WelcomeCards";

export function WorkspacePanel() {
  const { content, setContent, clearContent } = useWorkspace();

  useFrontendTool({
    name: "display_in_workspace",
    description:
      "Show a table or document in the main workspace panel when chat space is too narrow for the full result.",
    parameters: [
      {
        name: "type",
        type: "string",
        description: "Content type: table or document",
        required: true,
      },
      {
        name: "title",
        type: "string",
        description: "Title shown in the workspace header",
        required: true,
      },
      {
        name: "columns",
        type: "string[]",
        description: "Table column headers (table type only)",
      },
      {
        name: "rows",
        type: "object[]",
        description: "Table row values as arrays of strings aligned to columns (table type only)",
      },
      {
        name: "mimeType",
        type: "string",
        description: "Document MIME type (document type only)",
      },
      {
        name: "url",
        type: "string",
        description: "Document data URL (document type only)",
      },
      {
        name: "filename",
        type: "string",
        description: "Original filename (document type only)",
      },
    ],
    handler: async ({
      type,
      title,
      columns,
      rows,
      mimeType,
      url,
      filename,
    }: {
      type: string;
      title: string;
      columns?: string[];
      rows?: Array<string[] | Record<string, unknown>>;
      mimeType?: string;
      url?: string;
      filename?: string;
    }) => {
      if (type === "table" && columns && rows) {
        const normalizedRows = rows.map((row) =>
          Array.isArray(row) ? row.map((cell) => String(cell ?? "")) : columns.map(() => "")
        );
        setContent({ type: "table", title, columns, rows: normalizedRows });
        return "Displayed table in workspace.";
      }
      if (type === "document" && mimeType && url) {
        setContent({ type: "document", title, mimeType, url, filename });
        return "Displayed document in workspace.";
      }
      return "Workspace display skipped: missing fields.";
    },
  });

  if (!content) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <WelcomeCards />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-end border-b border-zinc-200 bg-white px-4 py-2">
        <button
          type="button"
          onClick={clearContent}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50"
        >
          Back to welcome
        </button>
      </div>
      <div className="min-h-0 flex-1">
        {content.type === "table" ? (
          <DataTableView table={content} />
        ) : (
          <DocumentPreview document={content} />
        )}
      </div>
    </div>
  );
}
