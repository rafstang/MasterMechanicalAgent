"""Tests for HouseCall Pro allowlist validation."""

from __future__ import annotations

import pytest

from src.agents.MasterMechanicalAgent.hcp.allowlist import (
    AllowlistError,
    build_field_diff,
    validate_and_build_patch_body,
)


def test_customer_scalar_fields_allowed():
    body = validate_and_build_patch_body(
        "customer",
        {"mobile_number": "4805550100", "email": "tech@example.com"},
    )
    assert body == {"mobile_number": "4805550100", "email": "tech@example.com"}


def test_customer_denies_financial_fields():
    with pytest.raises(AllowlistError, match="total_amount"):
        validate_and_build_patch_body("customer", {"total_amount": 100})


def test_customer_service_address_requires_service_type():
    body = validate_and_build_patch_body(
        "customer",
        {
            "addresses": [
                {
                    "type": "service",
                    "street": "123 Main St",
                    "city": "Phoenix",
                    "state": "AZ",
                    "zip": "85001",
                }
            ]
        },
    )
    assert body["addresses"][0]["type"] == "service"
    assert body["addresses"][0]["street"] == "123 Main St"


def test_customer_rejects_billing_address_type():
    with pytest.raises(AllowlistError, match="service"):
        validate_and_build_patch_body(
            "customer",
            {"addresses": [{"type": "billing", "street": "123 Main St"}]},
        )


def test_job_work_status_blocks_cancel_targets():
    with pytest.raises(AllowlistError, match="user_canceled"):
        validate_and_build_patch_body(
            "job",
            {"work_status": "user_canceled"},
            current_record={"work_status": "in_progress"},
        )


def test_job_work_timestamps_allowed():
    body = validate_and_build_patch_body(
        "job",
        {"work_timestamps": {"on_my_way_at": "2026-06-19T14:00:00Z"}},
        current_record={"work_status": "scheduled"},
    )
    assert body["work_timestamps"]["on_my_way_at"] == "2026-06-19T14:00:00Z"


def test_build_field_diff_for_job_status():
    diff = build_field_diff(
        "job",
        {"work_status": "scheduled"},
        {"work_status": "in_progress"},
    )
    assert diff == [
        {
            "field": "work_status",
            "before": "scheduled",
            "after": "in_progress",
        }
    ]
