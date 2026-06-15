from unittest.mock import MagicMock

import pytest
from ag_ui.core import RunAgentInput
from starlette.requests import Request

from src.agents.MasterMechanicalAgent import ag_ui_app


def test_user_id_from_request_uses_headers():
    inp = RunAgentInput(
        thread_id="t1",
        run_id="r1",
        state={"headers": {"user_id": "oauth-sub-42"}},
        messages=[],
        tools=[],
        context=[],
        forwarded_props={},
    )
    assert ag_ui_app._user_id_from_request(inp) == "oauth-sub-42"


def test_user_id_from_request_anonymous_when_missing():
    inp = RunAgentInput(
        thread_id="t1",
        run_id="r1",
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props={},
    )
    assert ag_ui_app._user_id_from_request(inp) == "anonymous"


@pytest.mark.asyncio
async def test_extract_trusted_identity_headers_overrides_spoofed_client_state():
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"x-user-id", b"server-id"),
                (b"x-user-email", b"real@example.com"),
                (b"x-user-name", b"Real User"),
            ],
            "method": "POST",
            "path": "/",
        }
    )
    input_data = RunAgentInput(
        thread_id="t1",
        run_id="r1",
        state={
            "headers": {
                "user_id": "spoofed-id",
                "user_email": "attacker@evil.com",
                "user_name": "Attacker",
                "locale": "en-US",
            }
        },
        messages=[],
        tools=[],
        context=[],
        forwarded_props={},
    )

    merged = await ag_ui_app._extract_trusted_identity_headers(request, input_data)
    headers = merged["headers"]
    assert headers["user_id"] == "server-id"
    assert headers["user_email"] == "real@example.com"
    assert headers["user_name"] == "Real User"
    assert headers["locale"] == "en-US"


@pytest.mark.asyncio
async def test_invoker_guard_rejects_post_without_token(monkeypatch):
    monkeypatch.setenv("AG_UI_INVOKER_SECRET", "test-secret")
    monkeypatch.delenv("AG_UI_ALLOW_UNAUTHENTICATED", raising=False)

    request = Request({"type": "http", "headers": [], "method": "POST", "path": "/"})
    called = {"value": False}

    async def call_next(_req):
        called["value"] = True
        return MagicMock()

    response = await ag_ui_app.ag_ui_invoker_guard(request, call_next)
    assert response.status_code == 401
    assert called["value"] is False


@pytest.mark.asyncio
async def test_invoker_guard_allows_post_with_valid_token(monkeypatch):
    monkeypatch.setenv("AG_UI_INVOKER_SECRET", "test-secret")

    request = Request(
        {
            "type": "http",
            "headers": [(b"x-ag-ui-token", b"test-secret")],
            "method": "POST",
            "path": "/",
        }
    )
    called = {"value": False}

    async def call_next(_req):
        called["value"] = True
        return MagicMock()

    await ag_ui_app.ag_ui_invoker_guard(request, call_next)
    assert called["value"] is True


def test_validate_invoker_config_requires_secret_when_not_dev(monkeypatch):
    monkeypatch.delenv("AG_UI_ALLOW_UNAUTHENTICATED", raising=False)
    monkeypatch.delenv("AG_UI_INVOKER_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="AG_UI_INVOKER_SECRET"):
        ag_ui_app._validate_invoker_config()


def test_validate_invoker_config_allows_dev_flag(monkeypatch):
    monkeypatch.setenv("AG_UI_ALLOW_UNAUTHENTICATED", "true")
    monkeypatch.delenv("AG_UI_INVOKER_SECRET", raising=False)
    ag_ui_app._validate_invoker_config()
