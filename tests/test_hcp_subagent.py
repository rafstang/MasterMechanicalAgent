"""Tests for HouseCall Pro subagent wiring."""

from __future__ import annotations

from google.adk.tools.agent_tool import AgentTool

from src.agents.MasterMechanicalAgent import root_agent
from src.agents.MasterMechanicalAgent.agent import _AGENT_INSTRUCTION
from src.agents.MasterMechanicalAgent.subagents.hcp_records_agent import hcp_records_agent


def test_root_agent_has_hcp_subagent_tool():
    agent_tools = [
        tool
        for tool in root_agent.tools
        if isinstance(tool, AgentTool) and getattr(tool, "agent", None) is hcp_records_agent
    ]
    assert len(agent_tools) == 1


def test_root_instruction_delegates_hcp_updates():
    assert "hcp_records_agent" in _AGENT_INSTRUCTION
    assert "HouseCall Pro updates" in _AGENT_INSTRUCTION


def test_hcp_subagent_has_expected_tools():
    tool_names = {getattr(tool, "name", tool.__class__.__name__) for tool in hcp_records_agent.tools}
    assert "hcp_propose_update" in tool_names
    assert "hcp_apply_update" in tool_names
    assert "hcp_get_customer" in tool_names
    assert "hcp_get_job" in tool_names
