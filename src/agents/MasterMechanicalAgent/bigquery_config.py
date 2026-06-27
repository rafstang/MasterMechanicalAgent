"""Shared BigQuery toolset configuration for Master Mechanical agents."""

from __future__ import annotations

import os

import google.auth
from google.adk.tools.bigquery.bigquery_credentials import BigQueryCredentialsConfig
from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

BIGQUERY_PROJECT_ID = (
    os.environ.get("GOOGLE_CLOUD_PROJECT") or "mastermechanical"
).strip()
BIGQUERY_DATASET_ID = "dev_Master_Mechanical"
BIGQUERY_DATASET_REF = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}"

_DEFAULT_TOOL_FILTER = [
    "list_dataset_ids",
    "get_dataset_info",
    "list_table_ids",
    "get_table_info",
    "execute_sql",
]

_LOOKUP_TOOL_FILTER = [
    "get_table_info",
    "execute_sql",
]

tool_config = BigQueryToolConfig(
    write_mode=WriteMode.BLOCKED,
    compute_project_id=BIGQUERY_PROJECT_ID,
    application_name="mastermechanical-agent",
)


def _credentials_config() -> BigQueryCredentialsConfig:
    creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_file and os.path.exists(creds_file):
        creds, _ = google.auth.load_credentials_from_file(creds_file)
        return BigQueryCredentialsConfig(credentials=creds)
    application_default_credentials, _ = google.auth.default()
    return BigQueryCredentialsConfig(credentials=application_default_credentials)


def make_bigquery_toolset(
    *,
    tool_filter: list[str] | None = None,
) -> BigQueryToolset:
    return BigQueryToolset(
        credentials_config=_credentials_config(),
        bigquery_tool_config=tool_config,
        tool_filter=tool_filter or _DEFAULT_TOOL_FILTER,
    )


bigquery_toolset = make_bigquery_toolset()
hcp_lookup_bigquery_toolset = make_bigquery_toolset(tool_filter=_LOOKUP_TOOL_FILTER)
