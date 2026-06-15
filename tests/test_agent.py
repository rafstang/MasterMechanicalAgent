from src.agents.MasterMechanicalAgent import root_agent
from src.agents.MasterMechanicalAgent.agent import (
    _AGENT_INSTRUCTION,
    _instruction_with_session_identity,
    _on_model_error_callback,
)
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


def test_agent_instruction_documents_bigquery_project_id():
    assert "project_id" in _AGENT_INSTRUCTION
    assert "mastermechanical.dev_Master_Mechanical" in _AGENT_INSTRUCTION
    assert "Never" in _AGENT_INSTRUCTION or "never" in _AGENT_INSTRUCTION
    assert 'project_id="mastermechanical"' in _AGENT_INSTRUCTION


def test_bigquery_tool_config_pins_compute_project():
    from src.agents.MasterMechanicalAgent.agent import (
        BIGQUERY_PROJECT_ID,
        tool_config,
    )

    assert BIGQUERY_PROJECT_ID == "mastermechanical"
    assert tool_config.compute_project_id == "mastermechanical"


def test_agent_instruction_documents_money_in_cents():
    assert "cents" in _AGENT_INSTRUCTION.lower() or "pennies" in _AGENT_INSTRUCTION.lower()
    assert "/ 100" in _AGENT_INSTRUCTION


def test_agent_instruction_requires_workspace_for_long_tables():
    assert "display_in_workspace" in _AGENT_INSTRUCTION
    assert "Markdown table" in _AGENT_INSTRUCTION or "markdown table" in _AGENT_INSTRUCTION.lower()
    assert "pseudo-table" in _AGENT_INSTRUCTION


def test_agent_instruction_never_uses_company_name_for_customer_display():
    assert "Customer display name" in _AGENT_INSTRUCTION
    assert "not the end-customer" in _AGENT_INSTRUCTION or "not the customer" in _AGENT_INSTRUCTION.lower()
    assert "Never use `customers.company_name`" in _AGENT_INSTRUCTION


def test_agent_instruction_prefers_customer_job_columns_over_ids():
    assert "User-facing job lists" in _AGENT_INSTRUCTION
    assert "customer" in _AGENT_INSTRUCTION.lower()
    assert "start_az" in _AGENT_INSTRUCTION


def test_agent_instruction_documents_employees_table():
    assert "dev_Master_Mechanical.employees" in _AGENT_INSTRUCTION
    assert "assigned_employees" in _AGENT_INSTRUCTION
    assert "dispatched_employees_ids" in _AGENT_INSTRUCTION


def test_instruction_includes_oauth_subject_when_email_present():
    class _Ctx:
        state = {
            "headers": {
                "user_email": "owner@example.com",
                "user_id": "oauth-subject-123",
                "user_name": "Test User",
            }
        }

    text = _instruction_with_session_identity(_Ctx())  # type: ignore[arg-type]
    assert "oauth-subject-123" in text
    assert "OAuth subject" in text


def test_on_model_error_callback_handles_503():
    class _StateDict(dict):
        pass

    class _Ctx:
        def __init__(self):
            self.state = _StateDict()

    response = _on_model_error_callback(
        _Ctx(),  # type: ignore[arg-type]
        llm_request=None,  # type: ignore[arg-type]
        error=Exception("503 Service Unavailable: UNAVAILABLE"),
    )
    assert response is not None
    assert response.content is not None
    assert response.content.parts
    assert "temporarily overloaded" in (response.content.parts[0].text or "")
