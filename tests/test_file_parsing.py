from src.agents.MasterMechanicalAgent.file_parsing import summarize_csv_bytes


def test_summarize_csv_bytes_includes_columns_and_rows():
    data = b"name,role\nAlice,Owner\nBob,Tech\n"
    summary = summarize_csv_bytes(data, "team.csv")
    assert "team.csv" in summary
    assert "name" in summary
    assert "role" in summary
    assert "Alice" in summary
    assert "Bob" in summary


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
