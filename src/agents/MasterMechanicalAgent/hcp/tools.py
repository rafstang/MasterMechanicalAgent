"""ADK tools for HouseCall Pro read and allowlisted write operations."""

from __future__ import annotations

import json
from typing import Any, Literal

from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

from src.agents.MasterMechanicalAgent.hcp.allowlist import (
    AllowlistError,
    ResourceType,
    build_field_diff,
    validate_and_build_patch_body,
)
from src.agents.MasterMechanicalAgent.hcp.client import HcpApiError, HcpClient
from src.agents.MasterMechanicalAgent.hcp.confirmation import (
    audit_log_apply,
    clear_pending_update,
    format_diff_for_user,
    require_authenticated_user,
    store_pending_update,
    validate_apply_allowed,
)


async def hcp_get_customer(customer_id: str, tool_context: ToolContext) -> str:
    """Fetch the current customer record from HouseCall Pro by id.

    Use before proposing updates so values are live, not from BigQuery.
    """
    del tool_context
    customer_id = str(customer_id or "").strip()
    if not customer_id:
        return "customer_id is required."

    try:
        client = HcpClient()
        record = await client.get_customer(customer_id)
    except (HcpApiError, PermissionError) as exc:
        return str(exc)

    return json.dumps(record, indent=2, default=str)


async def hcp_get_job(job_id: str, tool_context: ToolContext) -> str:
    """Fetch the current job record from HouseCall Pro by id.

    Use before proposing updates so values are live, not from BigQuery.
    """
    del tool_context
    job_id = str(job_id or "").strip()
    if not job_id:
        return "job_id is required."

    try:
        client = HcpClient()
        record = await client.get_job(job_id)
    except (HcpApiError, PermissionError) as exc:
        return str(exc)

    return json.dumps(record, indent=2, default=str)


async def hcp_propose_update(
    resource_type: Literal["customer", "job"],
    resource_id: str,
    changes: dict[str, Any],
    tool_context: ToolContext,
) -> str:
    """Validate allowlisted changes, show a before/after diff, and store a pending update.

    Does not call HouseCall Pro write APIs. After this tool returns, stop and ask the
    technician to confirm before calling hcp_apply_update.
    """
    resource_id = str(resource_id or "").strip()
    if not resource_id:
        return "resource_id is required."

    try:
        user_email = require_authenticated_user(tool_context)
        client = HcpClient()
        if resource_type == "customer":
            current = await client.get_customer(resource_id)
        else:
            current = await client.get_job(resource_id)

        patch_body = validate_and_build_patch_body(
            resource_type,
            changes,
            current_record=current,
        )
        diff = build_field_diff(resource_type, current, patch_body)
        token = store_pending_update(
            tool_context,
            resource_type=resource_type,
            resource_id=resource_id,
            patch_body=patch_body,
            diff=diff,
            user_email=user_email,
        )
    except (AllowlistError, HcpApiError, PermissionError, ValueError) as exc:
        return str(exc)

    return format_diff_for_user(
        resource_type=resource_type,
        resource_id=resource_id,
        diff=diff,
        confirmation_token=token,
    )


async def hcp_apply_update(confirmation_token: str, tool_context: ToolContext) -> str:
    """Apply the pending HouseCall Pro update after explicit user confirmation.

    Only call this after the user replies yes/confirm to a hcp_propose_update diff.
    """
    try:
        pending = validate_apply_allowed(tool_context, confirmation_token)
        user_email = require_authenticated_user(tool_context)
        resource_type: ResourceType = pending["resource_type"]
        resource_id = str(pending["resource_id"])
        patch_body = pending["patch_body"]
        token = str(pending["token"])

        client = HcpClient()
        if resource_type == "customer":
            updated = await client.patch_customer(resource_id, patch_body)
        else:
            updated = await client.patch_job(resource_id, patch_body)

        fields_changed = [entry["field"] for entry in pending.get("diff", [])]
        audit_log_apply(
            user_email=user_email,
            resource_type=resource_type,
            resource_id=resource_id,
            fields_changed=fields_changed,
            confirmation_token=token,
        )
        clear_pending_update(tool_context)
    except (HcpApiError, PermissionError, ValueError) as exc:
        return str(exc)

    return (
        f"Update applied to {resource_type} `{resource_id}`.\n\n"
        f"Changed fields: {', '.join(fields_changed)}.\n\n"
        "BigQuery may not reflect this change until the next sync. "
        "Use HouseCall Pro or hcp_get_* for the live record."
        f"\n\nUpdated record:\n{json.dumps(updated, indent=2, default=str)}"
    )


HCP_GET_CUSTOMER_TOOL = FunctionTool(hcp_get_customer)
HCP_GET_JOB_TOOL = FunctionTool(hcp_get_job)
HCP_PROPOSE_UPDATE_TOOL = FunctionTool(hcp_propose_update)
HCP_APPLY_UPDATE_TOOL = FunctionTool(hcp_apply_update)

HCP_TOOLS = [
    HCP_GET_CUSTOMER_TOOL,
    HCP_GET_JOB_TOOL,
    HCP_PROPOSE_UPDATE_TOOL,
    HCP_APPLY_UPDATE_TOOL,
]
