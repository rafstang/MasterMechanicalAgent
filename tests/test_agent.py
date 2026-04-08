from src.agents.MasterMechanicalAgent import root_agent
from src.agents.MasterMechanicalAgent.ag_ui_app import adk_middleware_agent


def test_root_agent_configured():
    assert root_agent.name == "master_mechanical_agent"
    assert root_agent.tools is not None
    assert len(root_agent.tools) > 0


def test_root_agent_has_status_callbacks():
    assert root_agent.before_model_callback is not None
    assert root_agent.after_model_callback is not None
    assert root_agent.before_tool_callback is not None
    assert root_agent.after_tool_callback is not None
    assert root_agent.after_agent_callback is not None


def test_ag_ui_middleware_status_features_enabled():
    assert getattr(adk_middleware_agent, "_emit_messages_snapshot", False) is True
    assert (
        getattr(adk_middleware_agent, "_streaming_function_call_arguments", False)
        is True
    )
