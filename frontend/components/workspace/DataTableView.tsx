"use client";

import type { WorkspaceTableContent } from "./WorkspaceContext";

function escapeCsvCell(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function toCsv(columns: string[], rows: string[][]): string {
  const header = columns.map(escapeCsvCell).join(",");
  const body = rows.map((row) => row.map((cell) => escapeCsvCell(cell ?? "")).join(",")).join("\n");
  return `${header}\n${body}`;
}

export type DataTableViewProps = {
  table: WorkspaceTableContent;
};

export function DataTableView({ table }: DataTableViewProps) {
  const downloadCsv = () => {
    const csv = toCsv(table.columns, table.rows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${table.title.replace(/\s+/g, "_").toLowerCase() || "export"}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-3">
        <h2 className="text-base font-semibold text-zinc-900">{table.title}</h2>
        <button
          type="button"
          onClick={downloadCsv}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50"
        >
          Export CSV
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full min-w-max border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-zinc-100">
            <tr>
              {table.columns.map((col) => (
                <th
                  key={col}
                  className="border-b border-zinc-200 px-4 py-2 text-left font-medium text-zinc-700"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-white even:bg-zinc-50/80">
                {table.columns.map((col, colIndex) => (
                  <td
                    key={`${rowIndex}-${col}`}
                    className="border-b border-zinc-100 px-4 py-2 align-top text-zinc-800"
                    title={row[colIndex] ?? ""}
                  >
                    <span className="block max-w-md truncate">{row[colIndex] ?? ""}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
