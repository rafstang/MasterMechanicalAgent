"""Server-side allowlists for HouseCall Pro write operations."""

from __future__ import annotations

from typing import Any, Literal

ResourceType = Literal["customer", "job"]

CUSTOMER_SCALAR_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "email",
        "mobile_number",
        "home_number",
        "work_number",
        "notes",
    }
)

SERVICE_ADDRESS_FIELDS = frozenset(
    {
        "street",
        "street_line_2",
        "city",
        "state",
        "zip",
        "country",
    }
)

JOB_SCALAR_FIELDS = frozenset({"description", "notes", "work_status"})

WORK_TIMESTAMP_FIELDS = frozenset({"on_my_way_at", "started_at", "completed_at"})

DENIED_TOP_LEVEL_FIELDS = frozenset(
    {
        "total_amount",
        "outstanding_balance",
        "invoice_number",
        "assigned_employee_ids",
        "assigned_employees",
        "schedule",
        "lead_source",
        "company_name",
        "company_id",
        "tags",
        "customer_id",
        "id",
        "created_at",
        "updated_at",
    }
)

ALLOWED_WORK_STATUS_TARGETS = frozenset(
    {
        "scheduled",
        "in_progress",
        "complete",
        "completed_unrated",
    }
)

BLOCKED_WORK_STATUS_TARGETS = frozenset(
    {
        "unscheduled",
        "user_canceled",
        "pro_canceled",
    }
)


class AllowlistError(ValueError):
    """Raised when proposed changes include disallowed fields or values."""


def validate_and_build_patch_body(
    resource_type: ResourceType,
    changes: dict[str, Any],
    *,
    current_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate `changes` and return the JSON body to send to HouseCall Pro."""
    if not isinstance(changes, dict) or not changes:
        raise AllowlistError("changes must be a non-empty object.")

    unknown = set(changes.keys()) & DENIED_TOP_LEVEL_FIELDS
    if unknown:
        raise AllowlistError(
            f"These fields cannot be updated: {', '.join(sorted(unknown))}."
        )

    if resource_type == "customer":
        return _build_customer_body(changes)
    if resource_type == "job":
        return _build_job_body(changes, current_record=current_record)
    raise AllowlistError(f"Unsupported resource_type: {resource_type}")


def _build_customer_body(changes: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key, value in changes.items():
        if key in CUSTOMER_SCALAR_FIELDS:
            body[key] = value
            continue
        if key == "addresses":
            body["addresses"] = _normalize_service_addresses(value)
            continue
        raise AllowlistError(
            f"Field '{key}' is not allowed on customers. "
            f"Allowed: {', '.join(sorted(CUSTOMER_SCALAR_FIELDS | {'addresses'}))}."
        )

    if not body:
        raise AllowlistError("No allowlisted customer fields were provided.")
    return body


def _normalize_service_addresses(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise AllowlistError("addresses must be a non-empty list.")

    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise AllowlistError(f"addresses[{index}] must be an object.")
        address_type = str(entry.get("type") or "service").strip().lower()
        if address_type != "service":
            raise AllowlistError(
                "Only service addresses may be updated (type must be 'service')."
            )
        payload: dict[str, Any] = {"type": "service"}
        if address_id := entry.get("id"):
            payload["id"] = str(address_id)
        for field in SERVICE_ADDRESS_FIELDS:
            if field in entry:
                payload[field] = entry[field]
        if len(payload) <= 1 and "id" not in payload:
            raise AllowlistError(
                f"addresses[{index}] must include at least one service address field."
            )
        normalized.append(payload)
    return normalized


def _build_job_body(
    changes: dict[str, Any],
    *,
    current_record: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key, value in changes.items():
        if key in JOB_SCALAR_FIELDS:
            if key == "work_status":
                _validate_work_status(value, current_record=current_record)
            body[key] = value
            continue
        if key == "work_timestamps":
            body["work_timestamps"] = _normalize_work_timestamps(value)
            continue
        raise AllowlistError(
            f"Field '{key}' is not allowed on jobs. "
            f"Allowed: description, notes, work_status, work_timestamps."
        )

    if not body:
        raise AllowlistError("No allowlisted job fields were provided.")
    return body


def _validate_work_status(
    value: Any,
    *,
    current_record: dict[str, Any] | None,
) -> None:
    status = str(value).strip()
    if status in BLOCKED_WORK_STATUS_TARGETS:
        raise AllowlistError(
            f"work_status '{status}' cannot be set by field technicians."
        )
    if status not in ALLOWED_WORK_STATUS_TARGETS:
        raise AllowlistError(
            f"work_status '{status}' is not an allowed target. "
            f"Allowed: {', '.join(sorted(ALLOWED_WORK_STATUS_TARGETS))}."
        )
    current = None
    if isinstance(current_record, dict):
        current = str(current_record.get("work_status") or "").strip() or None
    if current and current in BLOCKED_WORK_STATUS_TARGETS:
        raise AllowlistError(
            f"Cannot update a job whose current work_status is '{current}'."
        )


def _normalize_work_timestamps(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise AllowlistError("work_timestamps must be a non-empty object.")
    unknown = set(value.keys()) - WORK_TIMESTAMP_FIELDS
    if unknown:
        raise AllowlistError(
            f"Unsupported work_timestamps fields: {', '.join(sorted(unknown))}."
        )
    return {key: str(value[key]) for key in WORK_TIMESTAMP_FIELDS if key in value}


def build_field_diff(
    resource_type: ResourceType,
    current: dict[str, Any],
    patch_body: dict[str, Any],
) -> list[dict[str, str]]:
    """Return a list of {field, before, after} entries for user confirmation."""
    diffs: list[dict[str, str]] = []
    for key, after_val in patch_body.items():
        before_val = current.get(key)
        if key == "addresses":
            diffs.append(
                {
                    "field": "addresses (service)",
                    "before": _format_value(_service_address_summary(current.get("addresses"))),
                    "after": _format_value(_service_address_summary(after_val)),
                }
            )
            continue
        if key == "work_timestamps" and isinstance(after_val, dict):
            before_ts = before_val if isinstance(before_val, dict) else {}
            for ts_key, ts_after in after_val.items():
                diffs.append(
                    {
                        "field": f"work_timestamps.{ts_key}",
                        "before": _format_value(before_ts.get(ts_key)),
                        "after": _format_value(ts_after),
                    }
                )
            continue
        diffs.append(
            {
                "field": key,
                "before": _format_value(before_val),
                "after": _format_value(after_val),
            }
        )
    return diffs


def _service_address_summary(addresses: Any) -> dict[str, Any] | None:
    if not isinstance(addresses, list):
        return None
    for entry in addresses:
        if isinstance(entry, dict) and str(entry.get("type") or "").lower() == "service":
            return {k: entry.get(k) for k in sorted(SERVICE_ADDRESS_FIELDS | {"id", "type"}) if k in entry}
    return addresses[0] if addresses else None


def _format_value(value: Any) -> str:
    if value is None:
        return "(empty)"
    if isinstance(value, (dict, list)):
        return str(value)
    text = str(value).strip()
    return text if text else "(empty)"
