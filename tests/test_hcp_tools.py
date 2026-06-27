"""Tests for HouseCall Pro confirmation state and tools."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.MasterMechanicalAgent.hcp.confirmation import (
    PENDING_HCP_UPDATE_KEY,
    store_pending_update,
    validate_apply_allowed,
)
from src.agents.MasterMechanicalAgent.hcp.tools import (
    hcp_apply_update,
    hcp_propose_update,
)


class _StateDict(dict):
    pass


class _FakeToolContext:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.state: _StateDict = _StateDict()
        if headers:
            self.state["headers"] = headers


def test_validate_apply_requires_authenticated_user():
    ctx = _FakeToolContext()
    with pytest.raises(PermissionError, match="signed-in user"):
        validate_apply_allowed(ctx, "token-123")  # type: ignore[arg-type]


def test_validate_apply_requires_matching_token():
    ctx = _FakeToolContext({"user_email": "tech@example.com"})
    store_pending_update(
        ctx,  # type: ignore[arg-type]
        resource_type="job",
        resource_id="job-1",
        patch_body={"notes": "Checked in"},
        diff=[{"field": "notes", "before": "", "after": "Checked in"}],
        user_email="tech@example.com",
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_apply_allowed(ctx, "wrong-token")  # type: ignore[arg-type]


def test_validate_apply_rejects_expired_pending():
    ctx = _FakeToolContext({"user_email": "tech@example.com"})
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    ctx.state[PENDING_HCP_UPDATE_KEY] = {
        "token": "tok",
        "resource_type": "job",
        "resource_id": "job-1",
        "patch_body": {"notes": "x"},
        "diff": [],
        "user_email": "tech@example.com",
        "created_at": expired.isoformat(),
        "expires_at": expired.isoformat(),
    }
    with pytest.raises(ValueError, match="expired"):
        validate_apply_allowed(ctx, "tok")  # type: ignore[arg-type]
    assert PENDING_HCP_UPDATE_KEY not in ctx.state


@pytest.mark.asyncio
async def test_hcp_propose_update_stores_pending_state():
    ctx = _FakeToolContext({"user_email": "tech@example.com"})
    current_job = {"id": "job-1", "work_status": "scheduled", "notes": "Old"}

    with patch(
        "src.agents.MasterMechanicalAgent.hcp.tools.HcpClient"
    ) as client_cls:
        client = client_cls.return_value
        client.get_job = AsyncMock(return_value=current_job)
        result = await hcp_propose_update(
            "job",
            "job-1",
            {"work_status": "in_progress"},
            ctx,  # type: ignore[arg-type]
        )

    assert "Proposed job update" in result
    assert PENDING_HCP_UPDATE_KEY in ctx.state
    assert ctx.state[PENDING_HCP_UPDATE_KEY]["patch_body"] == {
        "work_status": "in_progress"
    }


@pytest.mark.asyncio
async def test_hcp_apply_update_sends_allowlisted_patch():
    ctx = _FakeToolContext({"user_email": "tech@example.com"})
    token = store_pending_update(
        ctx,  # type: ignore[arg-type]
        resource_type="job",
        resource_id="job-1",
        patch_body={"notes": "Arrived on site"},
        diff=[{"field": "notes", "before": "", "after": "Arrived on site"}],
        user_email="tech@example.com",
    )

    with patch(
        "src.agents.MasterMechanicalAgent.hcp.tools.HcpClient"
    ) as client_cls:
        client = client_cls.return_value
        client.patch_job = AsyncMock(return_value={"id": "job-1", "notes": "Arrived on site"})
        result = await hcp_apply_update(token, ctx)  # type: ignore[arg-type]
        client.patch_job.assert_awaited_once_with(
            "job-1",
            {"notes": "Arrived on site"},
        )

    assert "Update applied" in result
    assert PENDING_HCP_UPDATE_KEY not in ctx.state


@pytest.mark.asyncio
async def test_hcp_apply_update_fails_without_pending():
    ctx = _FakeToolContext({"user_email": "tech@example.com"})
    result = await hcp_apply_update("missing", ctx)  # type: ignore[arg-type]
    assert "No pending" in result
