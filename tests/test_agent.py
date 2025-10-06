# tests/test_agent.py

from src.agent.agent import MyAgent

def test_agent_runs(capfd):
    agent = MyAgent()
    agent.run()
    out, _ = capfd.readouterr()
    assert "Agent is running!" in out
