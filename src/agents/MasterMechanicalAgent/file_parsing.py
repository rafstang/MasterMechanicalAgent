"""Parse uploaded CSV and Excel files into compact text summaries for the agent."""

from __future__ import annotations

import csv
import io
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from typing_extensions import override

_MAX_PREVIEW_ROWS = 10
_MAX_CELL_CHARS = 120
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


def _truncate_cell(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= _MAX_CELL_CHARS:
        return text
    return text[: _MAX_CELL_CHARS - 1] + "…"


def _reject_oversized(data: bytes, filename: str) -> str | None:
    if len(data) > MAX_ATTACHMENT_BYTES:
        limit_mb = MAX_ATTACHMENT_BYTES // (1024 * 1024)
        return (
            f"**{filename}** exceeds the {limit_mb} MB attachment limit "
            f"({len(data):,} bytes)."
        )
    return None


def _markdown_table_preview(
    header: list[str],
    body: list[list[str]],
    meta_lines: list[str],
) -> str:
    lines = meta_lines + ["", "**Sample rows:**"]
    if not body:
        lines.append("(no data rows)")
        return "\n".join(lines)

    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in body[:_MAX_PREVIEW_ROWS]:
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    if len(body) > _MAX_PREVIEW_ROWS:
        lines.append(f"\n… and {len(body) - _MAX_PREVIEW_ROWS} more rows.")
    return "\n".join(lines)


def summarize_csv_bytes(data: bytes, filename: str = "upload.csv") -> str:
    """Return a compact markdown summary of a CSV file."""
    oversize = _reject_oversized(data, filename)
    if oversize:
        return oversize

    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return f"**{filename}** is empty."

    header = [_truncate_cell(cell) for cell in rows[0]]
    body = [[_truncate_cell(cell) for cell in row] for row in rows[1:]]
    meta = [
        f"**File:** {filename}",
        f"**Rows:** {len(body)} (excluding header)",
        f"**Columns ({len(header)}):** {', '.join(header)}",
    ]
    return _markdown_table_preview(header, body, meta)


def summarize_excel_bytes(data: bytes, filename: str = "upload.xlsx") -> str:
    """Return a compact markdown summary of the first sheet in an Excel workbook."""
    oversize = _reject_oversized(data, filename)
    if oversize:
        return oversize

    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook.active
    if sheet is None:
        return f"**{filename}** has no active sheet."

    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return f"**{filename}** is empty."

    header = [_truncate_cell(cell) for cell in header_row]
    body: list[list[str]] = []
    for row in rows_iter:
        if row is None:
            continue
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        body.append([_truncate_cell(cell) for cell in row])

    meta = [
        f"**File:** {filename}",
        f"**Sheet:** {sheet.title}",
        f"**Rows:** {len(body)} (excluding header)",
        f"**Columns ({len(header)}):** {', '.join(header)}",
    ]
    return _markdown_table_preview(header, body, meta)


def summarize_spreadsheet_from_artifact(
    artifact: types.Part, filename: str
) -> str:
    """Summarize CSV or Excel artifact bytes."""
    inline = artifact.inline_data
    if inline is None or inline.data is None:
        return f"Could not read bytes for **{filename}**."

    data = inline.data
    oversize = _reject_oversized(data, filename)
    if oversize:
        return oversize

    mime = (inline.mime_type or "").split(";", 1)[0].strip().lower()
    lower_name = filename.lower()
    if mime in {"text/csv", "application/csv"} or lower_name.endswith(".csv"):
        return summarize_csv_bytes(data, filename)
    if lower_name.endswith(".xlsx") or lower_name.endswith(".xls") or "spreadsheet" in mime or "excel" in mime:
        return summarize_excel_bytes(data, filename)
    if mime.startswith("text/") or lower_name.endswith(".txt"):
        text = data.decode("utf-8", errors="replace")
        preview = text[:4000]
        suffix = "\n… (truncated)" if len(text) > 4000 else ""
        return f"**File:** {filename}\n\n```\n{preview}{suffix}\n```"
    return (
        f"**{filename}** ({mime or 'unknown type'}) is attached. "
        "Use load_artifacts for PDFs/images or ask the user to clarify the format."
    )


class SummarizeSpreadsheetTool(BaseTool):
    """Summarize a tabular attachment already saved as a session artifact."""

    def __init__(self) -> None:
        super().__init__(
            name="summarize_spreadsheet",
            description=(
                "Summarize a CSV, text, or Excel file that the user attached in this session. "
                "Pass the artifact filename (for example the uploaded file name). "
                "Use after load_artifacts when you need structured column/row context."
            ),
        )

    @override
    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> str:
        filename = str(args.get("filename") or "").strip()
        if not filename:
            return "filename is required."

        artifact = await tool_context.load_artifact(filename)
        if artifact is None:
            return f"No artifact named '{filename}' in this session."

        return summarize_spreadsheet_from_artifact(artifact, filename)
