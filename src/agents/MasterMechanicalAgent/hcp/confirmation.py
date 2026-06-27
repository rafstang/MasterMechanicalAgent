"""Session-backed confirmation state for HouseCall Pro writes."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from google.adk.tools.tool_context import ToolContext

from src.agents.MasterMechanicalAgent.hcp.allowlist import ResourceType

logger = logging.getLogger(__name__)

PENDING_HCP_UPDATE_KEY = "pending_hcp_update"
PENDING_TTL = timedelta(minutes=10)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_user_email(tool_context: ToolContext) -> str:
    headers = tool_context.state.get("headers")
    if not isinstance(headers, dict):
        return ""
    return str(headers.get("user_email") or "").strip()


def require_authenticated_user(tool_context: ToolContext) -> str:
    email = get_user_email(tool_context)
    if not email:
        raise PermissionError(
            "HouseCall Pro updates require a signed-in user with a verified email."
        )
    return email


def store_pending_update(
    tool_context: ToolContext,
    *,
    resource_type: ResourceType,
    resource_id: str,
    patch_body: dict[str, Any],
    diff: list[dict[str, str]],
    user_email: str,
) -> str:
    token = str(uuid.uuid4())
    now = _utc_now()
    pending = {
        "token": token,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "patch_body": patch_body,
        "diff": diff,
        "user_email": user_email,
        "created_at": now.isoformat(),
        "expires_at": (now + PENDING_TTL).isoformat(),
    }
    tool_context.state[PENDING_HCP_UPDATE_KEY] = pending
    return token


def load_pending_update(tool_context: ToolContext) -> dict[str, Any] | None:
    pending = tool_context.state.get(PENDING_HCP_UPDATE_KEY)
    if not isinstance(pending, dict):
        return None
    return pending


def clear_pending_update(tool_context: ToolContext) -> None:
    tool_context.state.pop(PENDING_HCP_UPDATE_KEY, None)


def validate_apply_allowed(
    tool_context: ToolContext,
    confirmation_token: str,
) -> dict[str, Any]:
    """Validate that apply is allowed and return the pending update payload."""
    require_authenticated_user(tool_context)
    token = str(confirmation_token or "").strip()
    if not token:
        raise ValueError("confirmation_token is required.")

    pending = load_pending_update(tool_context)
    if not pending:
        raise ValueError(
            "No pending HouseCall Pro update. Call hcp_propose_update first and "
            "wait for user confirmation."
        )

    if str(pending.get("token") or "") != token:
        raise ValueError(
            "confirmation_token does not match the pending update. "
            "Call hcp_propose_update again if changes are still needed."
        )

    expires_at = _parse_iso(str(pending.get("expires_at") or ""))
    if expires_at is None or _utc_now() > expires_at:
        clear_pending_update(tool_context)
        raise ValueError(
            "The pending update expired. Call hcp_propose_update again."
        )

    user_email = get_user_email(tool_context)
    pending_email = str(pending.get("user_email") or "").strip()
    if pending_email and user_email.lower() != pending_email.lower():
        raise PermissionError(
            "Only the user who proposed the update may apply it."
        )

    return pending


def audit_log_apply(
  *,
  user_email: str,
  resource_type: str,
  resource_id: str,
  fields_changed: list[str],
  confirmation_token: str,
) -> None:
    logger.info(
        "hcp_update_applied user_email=%s resource_type=%s resource_id=%s "
        "fields=%s token=%s",
        user_email,
        resource_type,
        resource_id,
        ",".join(fields_changed),
        confirmation_token,
    )


def format_diff_for_user(
    *,
    resource_type: ResourceType,
    resource_id: str,
    diff: list[dict[str, str]],
    confirmation_token: str,
) -> str:
    lines = [
        f"**Proposed {resource_type} update** (`{resource_id}`)",
        "",
        "| Field | Before | After |",
        "| --- | --- | --- |",
    ]
    for entry in diff:
        lines.append(
            f"| {entry['field']} | {entry['before']} | {entry['after']} |"
        )
    lines.extend(
        [
            "",
            f"Confirmation token: `{confirmation_token}`",
            "",
            "Reply **yes** or **confirm** to apply this update, or describe changes "
            "you want instead. The update is **not** sent until you confirm.",
        ]
    )
    return "\n".join(lines)
