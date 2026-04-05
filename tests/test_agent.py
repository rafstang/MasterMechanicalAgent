from src.agents.MasterMechanicalAgent import root_agent


def test_root_agent_configured():
    assert root_agent.name == "master_mechanical_agent"
    assert root_agent.tools is not None
    assert len(root_agent.tools) > 0
