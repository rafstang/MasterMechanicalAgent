import io

from google.genai import types

from src.agents.MasterMechanicalAgent.file_parsing import (
    MAX_ATTACHMENT_BYTES,
    summarize_csv_bytes,
    summarize_excel_bytes,
    summarize_spreadsheet_from_artifact,
)


def test_summarize_csv_bytes_includes_columns_and_rows():
    data = b"name,role\nAlice,Owner\nBob,Tech\n"
    summary = summarize_csv_bytes(data, "team.csv")
    assert "team.csv" in summary
    assert "name" in summary
    assert "role" in summary
    assert "Alice" in summary
    assert "Bob" in summary


def test_summarize_csv_bytes_rejects_oversize():
    data = b"x" * (MAX_ATTACHMENT_BYTES + 1)
    summary = summarize_csv_bytes(data, "big.csv")
    assert "exceeds" in summary
    assert "big.csv" in summary


def test_summarize_excel_bytes_reads_first_sheet():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["col_a", "col_b"])
    ws.append(["1", "2"])
    buf = io.BytesIO()
    wb.save(buf)

    summary = summarize_excel_bytes(buf.getvalue(), "sample.xlsx")
    assert "sample.xlsx" in summary
    assert "Sheet1" in summary
    assert "col_a" in summary
    assert "1" in summary


def test_summarize_spreadsheet_from_artifact_text_preview():
    part = types.Part(
        inline_data=types.Blob(
            mime_type="text/plain",
            data=b"hello world",
        )
    )
    summary = summarize_spreadsheet_from_artifact(part, "notes.txt")
    assert "notes.txt" in summary
    assert "hello world" in summary


def test_summarize_spreadsheet_from_artifact_unknown_mime():
    part = types.Part(
        inline_data=types.Blob(
            mime_type="application/octet-stream",
            data=b"\x00\x01",
        )
    )
    summary = summarize_spreadsheet_from_artifact(part, "data.bin")
    assert "data.bin" in summary
    assert "load_artifacts" in summary


def test_root_agent_has_attachment_tools():
    from src.agents.MasterMechanicalAgent.agent import load_artifacts_tool
    from src.agents.MasterMechanicalAgent.file_parsing import SummarizeSpreadsheetTool
    from src.agents.MasterMechanicalAgent import root_agent

    assert load_artifacts_tool in root_agent.tools
    assert any(isinstance(tool, SummarizeSpreadsheetTool) for tool in root_agent.tools)


def test_agent_instruction_covers_attachments_and_display_name():
    from src.agents.MasterMechanicalAgent.agent import _AGENT_INSTRUCTION

    assert "load_artifacts" in _AGENT_INSTRUCTION
    assert "summarize_spreadsheet" in _AGENT_INSTRUCTION
    assert "display_name" in _AGENT_INSTRUCTION
    assert "display_in_workspace" in _AGENT_INSTRUCTION
