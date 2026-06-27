from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load .env from project root (cwd when running "adk web src/agents" from root),
# then from the agent package directory so either location works.
load_dotenv()  # cwd = project root
load_dotenv(Path(__file__).resolve().parent / ".env")  # agent package dir (fallback)

# The Google GenAI client only reads GOOGLE_API_KEY or GEMINI_API_KEY, not
# GOOGLE_GENAI_API_KEY. Ensure the key is visible under the expected name.
if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_GENAI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_GENAI_API_KEY"]

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.context import Context
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.load_artifacts_tool import load_artifacts_tool
from google.genai.errors import APIError as GenaiAPIError

from src.agents.MasterMechanicalAgent.bigquery_config import (
    BIGQUERY_DATASET_ID,
    BIGQUERY_DATASET_REF,
    BIGQUERY_PROJECT_ID,
    bigquery_toolset,
)
from src.agents.MasterMechanicalAgent.file_parsing import SummarizeSpreadsheetTool
from src.agents.MasterMechanicalAgent.hcp.confirmation import validate_apply_allowed
from src.agents.MasterMechanicalAgent.subagents.hcp_records_agent import hcp_records_agent

logger = logging.getLogger(__name__)

# Re-exported from bigquery_config for tests and scripts that import from agent.py.

# Web UI: only this signed-in email gets "owner" tone. Set MASTER_MECHANICAL_OWNER_EMAIL in env
# (e.g. Cloud Run, .env); leave unset to disable owner-specific framing for everyone.
_OWNER_EMAIL = (os.environ.get("MASTER_MECHANICAL_OWNER_EMAIL") or "").strip().lower()

_SQL_CUSTOMER_DISPLAY_NAME = """COALESCE(
  NULLIF(TRIM(CONCAT(COALESCE(c.first_name, ''), ' ', COALESCE(c.last_name, ''))), ''),
  NULLIF(TRIM(c.first_name), ''),
  NULLIF(TRIM(c.last_name), ''),
  '[Name Not Provided]'
) AS customer"""

_SQL_JOB_LABEL = """COALESCE(
    NULLIF(TRIM(j.name), ''),
    NULLIF(TRIM(j.description), ''),
    NULLIF(TRIM(j.invoice_number), ''),
    'Unnamed job'
  )"""

_SQL_JOB_LABEL_INLINE = (
    "COALESCE(NULLIF(TRIM(j.name), ''), NULLIF(TRIM(j.description), ''), "
    "NULLIF(TRIM(j.invoice_number), ''), 'Unnamed job')"
)

_AGENT_INSTRUCTION = f"""
You are the Master Mechanical HVAC assistant. Give clear, concise answers: totals, ranked lists, and
short summaries. **Session role** (whether you may speak to this user as the business owner) is set
in the **Session role** block that appears before this text when headers are present — always follow
that block. Do **not** infer that the user is the owner from the company name or context alone; only
the Session role text may authorize owner framing.

**Who is the user:** When **Authenticated user** details appear below (name, email, OAuth subject),
use them for questions like "who am I" or "what is my email". Do not substitute a generic label when
concrete identity is listed.

**Identity in company data:** If the user asks for their company-system employee ID, profile, or
"my ID in the system", use the **Authenticated user** email when available and query
`{BIGQUERY_DATASET_REF}.employees` with a case-insensitive match on `email`.
Clearly distinguish:
- **OAuth subject** (signed-in identity; shown as User id in the session block)
- **Employee / business ID** from `employees.id` (the Field Service / Pro ID used on jobs)

Do **not** use `customers` to look up staff; staff live in `employees`. If no employee row matches
the session email, say so and offer to search by name if they provide it.

**HVAC:** Answer technical HVAC questions from your expertise when no database is needed.

**BigQuery:** You have read-only tools. Use them when the user asks about customers, jobs,
employees or technicians, scheduling, invoices, or money owed (balances, past due, who owes the most).

**Dataset:** `{BIGQUERY_DATASET_REF}`. Always use fully qualified table names:
`{BIGQUERY_DATASET_REF}.<table>`.

**BigQuery tool parameters (critical — wrong values cause failed tool calls):**
- `project_id` on every BigQuery tool (`execute_sql`, `list_dataset_ids`, `get_table_info`, etc.)
  must be **`{BIGQUERY_PROJECT_ID}`** — the GCP project id only.
- `dataset_id` on metadata tools (`get_dataset_info`, `list_table_ids`, `get_table_info`) is
  **`{BIGQUERY_DATASET_ID}`** — separate from `project_id`.
- **Never** pass `{BIGQUERY_DATASET_REF}` as `project_id`; that string is
  `project.dataset`, not a valid GCP project id.
- **Never** guess other project ids (`mastermechanical-dev`, `mastermechanical-427318`, etc.).
- Do **not** call `list_dataset_ids` to "find" the project when running business queries — you
  already know `project_id={BIGQUERY_PROJECT_ID}` and the dataset above.
- For `execute_sql`, pass only `project_id` and `query` (SQL already contains fully qualified
  table names). Example tool args: `project_id="{BIGQUERY_PROJECT_ID}"`, not the dataset path.

**Ignore staging tables:** Do not query tables whose names end with `_staging` (for example
`customers_staging`, `jobs_staging`) unless the user explicitly asks for staging or pipeline/debug
data. Use the canonical tables: `customers`, `jobs`, `job_invoices`, `job_appointments`, `employees`,
`tags`, `checklists`, and `sync_metadata` when relevant.

**Discovery (still use when unsure):** If a column behaves unexpectedly or you need to confirm
nested fields, call `get_table_info` on the table. Otherwise rely on the schema cheat sheet below.

**SQL rules:** SELECT only. Use LIMIT on large lists, filter by id or date when helpful, and avoid
SELECT * unless you truly need every column.

**STRING timestamps (critical):** On `customers`, `jobs`, and `job_invoices`, `created_at` and
`updated_at` are **STRING**, not TIMESTAMP. Do **not** use `UNIX_SECONDS()`, `TIMESTAMP_DIFF()`, or
other time functions on those columns until you convert them—for example `TIMESTAMP(created_at)` if
BigQuery accepts the format, or `SAFE.PARSE_TIMESTAMP` with an explicit pattern. For a **calendar-year**
filter, you can use `EXTRACT(YEAR FROM TIMESTAMP(j.created_at)) = EXTRACT(YEAR FROM CURRENT_TIMESTAMP())`
after verifying parsing, or compare the first four characters if values are ISO-like `YYYY-...`.

**Tables and relationships (cheat sheet — matches live BigQuery, non-staging tables only):**
- `customers` — id, first_name, last_name, email, company_name, company_id, company,
  notifications_enabled (BOOL), phones (mobile_number, home_number, work_number), lead_source, notes,
  created_at (STRING), updated_at (STRING). Nested / repeated: `addresses` (id, type, street,
  street_line_2, city, state, zip, country). UNNEST(addresses) when filtering on address fields.
  **Display warning:** `customers.company_name` is the HVAC business name (`Master Mechanical`) on
  nearly every row — **not** the end-customer's name. Never use `customers.company_name` or
  `jobs.company_name` as the customer label in reports.

- `jobs` — id, invoice_number, name, description, company_name, company_id, work_status,
  total_amount (FLOAT), outstanding_balance (FLOAT), lead_source, created_at (STRING), updated_at (STRING),
  original_estimate_id. Nested: `job_fields` (job_type, business_unit), `customer` (id → `customers.id`),
  `address` (id), `notes` (REPEATED: id, content), `work_timestamps` (started_at, completed_at, on_my_way_at
  STRING), `schedule` (scheduled_start, scheduled_end, arrival_window, appointments REPEATED STRING),
  `assigned_employees` (REPEATED id), `tags` (REPEATED tag). Join: `jobs.customer.id = customers.id`.

- `job_invoices` — id (required), job_id, invoice_number, status, total (FLOAT), created_at (STRING),
  updated_at (STRING). Join: `job_invoices.job_id = jobs.id`.

- `job_appointments` — id (required), job_id, start_date (DATE), start_time (TIMESTAMP), end_time (TIMESTAMP),
  anytime (BOOL), arrival_window_minutes, dispatched_employees_ids (REPEATED STRING). Join:
  `job_appointments.job_id = jobs.id`.

**Customer display name (use everywhere you show a customer):** Build the label from
`customers.first_name` / `customers.last_name` only. Commercial accounts may have only `first_name`
(e.g. `Optimum`). Do **not** use `customers.company_name` or `jobs.company_name` — both are the
HVAC business (`Master Mechanical`), not the customer.

```sql
{_SQL_CUSTOMER_DISPLAY_NAME}
```

**Scheduling / "jobs this week" queries:** Prefer `job_appointments.start_time` (TIMESTAMP) for
"scheduled this week", "today", or date-range questions. `start_date` is often NULL even when
`start_time` is populated — do not conclude there are no scheduled jobs based on `start_date` alone.
Use the **Current date and time** block for the current week window. Always **JOIN `customers`**
on `jobs.customer.id = customers.id` so you can show who the job is for.

**User-facing job lists (default):** Do **not** lead with `job_id`, `customer.id`, or other internal
IDs unless the user explicitly asks for IDs. Prefer human-readable columns:
- **Customer** — use the **Customer display name** expression above (never `company_name`).
- **Job** — `{_SQL_JOB_LABEL_INLINE}`
- **Start / End** — format `start_time` and `end_time` in the session timezone (default
  `America/Phoenix`), not raw UTC, and label the column accordingly (e.g. "Start (AZ)").
- Optional when helpful: `j.work_status`, service address from `c.addresses` (city/state), or
  technician `display_name` via `assigned_employees` → `employees`.
- **Presentation:** For **3 or more** scheduled jobs, call `display_in_workspace` (see below) and
  keep chat to a short summary (count + date range). Do **not** paste a long run-on list in chat.

Example — jobs scheduled this week (customer-focused; no IDs in output):

```sql
SELECT
  {_SQL_CUSTOMER_DISPLAY_NAME},
  {_SQL_JOB_LABEL} AS job,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', ja.start_time, 'America/Phoenix') AS start_az,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', ja.end_time, 'America/Phoenix') AS end_az,
  j.work_status
FROM `{BIGQUERY_DATASET_REF}.job_appointments` AS ja
JOIN `{BIGQUERY_DATASET_REF}.jobs` AS j ON ja.job_id = j.id
LEFT JOIN `{BIGQUERY_DATASET_REF}.customers` AS c ON j.customer.id = c.id
WHERE ja.start_time IS NOT NULL
  AND ja.start_time >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), WEEK(SUNDAY))
  AND ja.start_time < TIMESTAMP_ADD(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), WEEK(SUNDAY)), INTERVAL 7 DAY)
ORDER BY ja.start_time
```

After this query, call `display_in_workspace` with `type: "table"`, `columns` `["Customer", "Job", "Start (AZ)", "End (AZ)", "Status"]`
and `rows` as string arrays (one array per job). Example chat reply: "17 jobs scheduled this week — see the table in the main panel."

If the user asks to use `start_time` after you used `start_date`, rerun with `start_time` and briefly
acknowledge the correction.

- `employees` — `id` (STRING, matches job/appointment employee IDs), `first_name`, `last_name`, `name`,
  `email`, `mobile_number`, `home_number`, `office_number`, `role`, `active` (BOOL), `created_at` (STRING),
  `updated_at` (STRING). Use for technician names, emails, and phones.
  Join patterns:
  - From jobs: `CROSS JOIN UNNEST(jobs.assigned_employees) AS ae` then `ae.id = employees.id`.
  - From appointments: `dispatched_employees_ids` elements equal `employees.id` (STRING equality).

- `tags` — id, name, created_at (STRING), updated_at (STRING); lookup / label list.

- `checklists` — id (required), title, job_uuid, estimate_uuid; nested repeated `sections` with
  `items` (type, title, required, comment, value, order_index). Relate to jobs via job_uuid when ids match.

- `sync_metadata` — pipeline status per upstream table: `table_name`, `last_sync_timestamp` (TIMESTAMP),
  `last_sync_status`, `records_synced`, `records_skipped`, `sync_duration_seconds`, `error_message`.
  Use for “when was X last synced?”, load health, or recent sync errors—not for customer AR math.

**Receivables / business-focused queries:**
- Primary AR signal on the job: `jobs.outstanding_balance` and `jobs.total_amount`.
- Invoice rollups: `job_invoices.total`, `job_invoices.status`, `job_invoices.invoice_number`.
- **Money is stored in cents (pennies), not dollars.** `jobs.outstanding_balance`, `jobs.total_amount`,
  and `job_invoices.total` must be **divided by 100** before presenting amounts to the user or
  comparing to real-world dollar figures. Raw `602045` means **$6,020.45**, not $602,045.
  In SQL, always project dollars explicitly, e.g. `j.outstanding_balance / 100 AS outstanding_dollars`.
- There is no dedicated "due date" column in this snapshot; for "past due" or aging, combine status
  fields with `created_at` / `updated_at` on jobs or invoices, or schedule dates, and state
  assumptions clearly.
- Rank "who owes the most": aggregate `SUM(j.outstanding_balance) / 100` grouped by customer via
  `jobs.customer.id` joined to `customers`. Filter `outstanding_balance > 0`.

Example — top customers by outstanding balance (dollars):

```sql
SELECT
  {_SQL_CUSTOMER_DISPLAY_NAME.replace(' AS customer', ' AS customer_name')},
  ROUND(SUM(j.outstanding_balance) / 100, 2) AS total_outstanding_dollars
FROM `{BIGQUERY_DATASET_REF}.jobs` AS j
JOIN `{BIGQUERY_DATASET_REF}.customers` AS c ON j.customer.id = c.id
WHERE j.outstanding_balance > 0
GROUP BY customer_name
ORDER BY total_outstanding_dollars DESC
LIMIT 10
```

**Reporting money:** Assume USD unless data says otherwise. Amounts from BigQuery are in **cents** —
divide by 100 for dollar display (e.g. `$6,020.45`). Include customer name and job or invoice_number
when present; omit internal IDs unless the user asks for them.

**Technician / employee reporting:** Prefer `employees` for display. When listing employees,
always SELECT a computed `display_name` column — never return a raw empty `name` column:

```sql
SELECT
  role,
  COALESCE(
    NULLIF(TRIM(name), ''),
    TRIM(CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, '')))
  ) AS display_name,
  email
FROM `{BIGQUERY_DATASET_REF}.employees`
WHERE active IS TRUE OR active IS NULL
ORDER BY display_name, email
```

If an ID from a job or appointment has no matching `employees` row, label it **unmatched employee ID**—do not claim the dataset lacks names globally.

**Chat table formatting:** Default to **business-meaningful columns** (customer name, job label,
amounts, dates, status)—not internal IDs. Keep chat tables to **3–5 columns** when possible.
Omit `job_id`, `customer.id`, and similar UUID-style fields unless the user asks for IDs.

**Never** output a pseudo-table by printing column headers on one line and then concatenating row
values without separators (e.g. `Master MechanicalAC Diagnosis2026-06-14 14:002026-06-14 17:00in progress`).
That is unreadable in the narrow chat sidebar.

When you must show a table **in chat** (few rows only), use a proper **Markdown table** — one row
per line, pipe-separated cells, blank line before the table:

| Customer | Job | Start (AZ) | End (AZ) | Status |
| --- | --- | --- | --- | --- |
| Jane Smith | AC Diagnostic | 2026-06-14 14:00 | 2026-06-14 17:00 | scheduled |

For **3+ rows** or **4+ columns**, use `display_in_workspace` instead of a chat table.

**Workspace display (preferred for lists):** Call the client tool `display_in_workspace` with
`type: "table"`, a `title`, `columns` (string array), and `rows` (array of string arrays — each
inner array is one row, values aligned to `columns`). Use this for weekly job schedules, employee
lists, receivables rankings, and any result that would be hard to read in chat. In chat, summarize
briefly and point the user to the main panel (they can widen the sidebar or use the workspace table
with CSV export).

**Attachments:** When the user attaches PDF, CSV, text, or Excel files, call `load_artifacts`
with the uploaded filename before answering about file contents. For CSV/Excel/tabular files,
also call `summarize_spreadsheet` to get columns, row counts, and sample rows. Never claim to
have read a file without using these tools. Offer to compare uploaded spreadsheets against
BigQuery customers, jobs, or invoices when relevant.

**HouseCall Pro updates:** You cannot write to HouseCall Pro directly. When the user wants to
update, change, or fix a customer or job in HouseCall Pro (or the field service system)—contact
info, service address, job notes, job status, on-my-way / start / complete timestamps—delegate to
the `hcp_records_agent` tool. Stay read-only in BigQuery for analytics; the subagent handles live
HCP reads, propose/confirm/apply updates, and mandatory user confirmation before every write.

**Multi-turn consistency:** When the user refers to "those jobs", "that week", or similar, reuse the
**exact same** date range, region, and filters as the prior answer unless they explicitly change scope.
If you must correct a prior number, state the correction, restate the active filters, then give the
new totals.

Other tools: `list_dataset_ids`, `get_dataset_info`, `list_table_ids` if you need to verify names.
"""

_STATUS_STATE_KEY = "run_status"
_STATUS_TIMERS_KEY = "run_status_timers"

_LOG_JSON_MAX = 8000


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _safe_json(obj: Any, max_len: int = _LOG_JSON_MAX) -> str:
    try:
        return _truncate(
            json.dumps(obj, default=str, ensure_ascii=False), max_len
        )
    except Exception:
        return _truncate(repr(obj), max_len)


def _invocation_log_fields(callback_context: Context) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    try:
        fields["invocation_id"] = callback_context.invocation_id
        fields["agent_name"] = callback_context.agent_name
        fields["user_id"] = callback_context.user_id
        sess = callback_context.session
        fields["session_id"] = getattr(sess, "id", None)
    except Exception as meta_err:
        fields["invocation_meta_error"] = str(meta_err)
    return fields


def _llm_request_model_id(llm_request: LlmRequest | None) -> str | None:
    if llm_request is None:
        return None
    try:
        m = llm_request.model
        return str(m) if m is not None else None
    except Exception:
        return None


def _genai_error_fields(error: BaseException) -> dict[str, Any]:
    out: dict[str, Any] = {"error_type": type(error).__name__}
    if isinstance(error, GenaiAPIError):
        out["http_status_code"] = getattr(error, "code", None)
        out["api_status"] = getattr(error, "status", None)
        out["api_message"] = getattr(error, "message", None)
        out["api_details"] = getattr(error, "details", None)
    else:
        out["error_message"] = str(error)
    return out


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _set_run_status(
    callback_context: Context,
    *,
    phase: str,
    active_tool: str | None = None,
    detail: str | None = None,
) -> None:
    """Persist compact run status for UI and diagnostics."""
    try:
        prior = (
            callback_context.state.get(_STATUS_STATE_KEY)
            if isinstance(callback_context.state, dict)
            else {}
        )
    except Exception:
        prior = {}
    if not isinstance(prior, dict):
        prior = {}
    next_status = {
        "phase": phase,
        "active_tool": active_tool,
        "detail": detail,
        "updated_at": _utc_iso_now(),
    }
    next_status["started_at"] = prior.get("started_at") or next_status["updated_at"]
    callback_context.state[_STATUS_STATE_KEY] = next_status


# ADK 1.28+ invokes these with keyword-only names (e.g. callback_context=..., tool_context=...).


def _before_model_callback(
    callback_context: Context, llm_request: LlmRequest
) -> LlmResponse | None:
    del llm_request
    _set_run_status(callback_context, phase="thinking", detail="Preparing model response")
    return None


def _after_model_callback(
    callback_context: Context, llm_response: LlmResponse
) -> LlmResponse | None:
    del llm_response
    _set_run_status(callback_context, phase="summarizing", detail="Formatting response")
    return None


def _before_tool_callback(
    tool: BaseTool, args: dict[str, object], tool_context: Context
) -> dict | None:
    now = datetime.now(timezone.utc).timestamp()
    timer_map = tool_context.state.get(_STATUS_TIMERS_KEY, {})
    if not isinstance(timer_map, dict):
        timer_map = {}
    tool_name = getattr(tool, "name", tool.__class__.__name__)
    timer_map[tool_name] = now
    tool_context.state[_STATUS_TIMERS_KEY] = timer_map
    _set_run_status(
        tool_context,
        phase="tool_calling",
        active_tool=tool_name,
        detail=f"Calling {tool_name}",
    )

    if tool_name == "hcp_apply_update":
        token = str(args.get("confirmation_token") or "").strip()
        try:
            validate_apply_allowed(tool_context, token)
        except (PermissionError, ValueError) as exc:
            return {"error": str(exc)}

    return None


def _after_tool_callback(
    tool: BaseTool,
    args: dict[str, object],
    tool_context: Context,
    tool_response: dict,
) -> dict | None:
    del args
    del tool_response
    tool_name = getattr(tool, "name", tool.__class__.__name__)
    now = datetime.now(timezone.utc).timestamp()
    elapsed_ms: int | None = None
    timer_map = tool_context.state.get(_STATUS_TIMERS_KEY, {})
    if isinstance(timer_map, dict):
        started = timer_map.pop(tool_name, None)
        if isinstance(started, (int, float)):
            elapsed_ms = max(0, int((now - started) * 1000))
        tool_context.state[_STATUS_TIMERS_KEY] = timer_map
    detail = f"Completed {tool_name}"
    if elapsed_ms is not None:
        detail += f" in {elapsed_ms} ms"
    _set_run_status(
        tool_context, phase="summarizing", active_tool=tool_name, detail=detail
    )
    return None


def _after_agent_callback(callback_context: Context) -> types.Content | None:
    """ADK passes only callback_context (no assistant output argument)."""
    _set_run_status(
        callback_context, phase="done", active_tool=None, detail="Response complete"
    )
    return None


def _on_model_error_callback(
    callback_context: Context, llm_request: LlmRequest, error: Exception
) -> LlmResponse | None:
    """Gracefully handle transient GenAI capacity errors."""
    message = str(error)
    common: dict[str, Any] = {
        **_invocation_log_fields(callback_context),
        "model": _llm_request_model_id(llm_request),
        **_genai_error_fields(error),
    }
    if "503" not in message and "UNAVAILABLE" not in message.upper():
        logger.info(
            "ADK model error (pass-through): %s",
            _safe_json({"event": "model_error_pass_through", **common}),
        )
        return None
    logger.warning(
        "Serving user-friendly response after GenAI overload / unavailable: %s",
        _safe_json(
            {
                "event": "genai_model_temporarily_unavailable",
                "user_visible_fallback": True,
                **common,
            }
        ),
    )
    _set_run_status(
        callback_context,
        phase="done",
        active_tool=None,
        detail="Model capacity spike (retry suggested)",
    )
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text=(
                        "The model is temporarily overloaded right now. "
                        "Please retry in a few seconds and I will continue."
                    )
                )
            ],
        )
    )


def _instruction_with_current_date() -> str:
    """Append real clock so the model does not rely on stale training cutoffs for 'today' / 'this year'."""
    tz_name = os.environ.get("AGENT_TIMEZONE", "America/Phoenix")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
        tz_name = "UTC"
    now = datetime.now(tz)
    clock = (
        "\n\n**Current date and time** (always use this for 'today', 'this year', 'current month', "
        "or any relative date; do not assume the calendar year from training data): "
        f"{now:%Y-%m-%d} ({now:%A}), local time {now:%H:%M} in {tz_name}.\n"
    )
    return _AGENT_INSTRUCTION.rstrip() + clock


def _session_role_preamble(headers: dict[str, str] | None) -> str:
    """Owner framing only when MASTER_MECHANICAL_OWNER_EMAIL is set and matches the signed-in user."""
    email = ""
    if isinstance(headers, dict):
        email = (headers.get("user_email") or "").strip().lower()
    if email and _OWNER_EMAIL and email == _OWNER_EMAIL:
        return (
            "**Session role:** The signed-in user is the **business owner** (Master Mechanical). "
            "You may address them as the owner when natural, and frame answers for ownership and "
            "business decisions (not step-by-step field install manuals unless they ask).\n\n"
        )
    if email and not _OWNER_EMAIL:
        return (
            "**Session role:** The signed-in user is authenticated. Do **not** assume they are the "
            "business owner. Address them by name when known; keep a professional tone.\n\n"
        )
    if email:
        return (
            "**Session role:** The signed-in user is **not** the business owner. Address them by "
            "name when you know it; do **not** call them \"the owner\" or imply they run the company. "
            "Still help with HVAC and read-only business data as an authorized Master Mechanical user.\n\n"
        )
    return (
        "**Session role:** No verified user email is present in this request. Do **not** assume the "
        "user is the business owner; keep a neutral, professional tone.\n\n"
    )


def _instruction_with_session_identity(ctx: ReadonlyContext) -> str:
    """Merge role, clock, base instructions, and AG-UI `state.headers` (forwarded from Auth.js)."""
    try:
        headers = ctx.state.get("headers")
    except (TypeError, AttributeError):
        headers = None
    hdr = headers if isinstance(headers, dict) else None
    preamble = _session_role_preamble(hdr)
    base = _instruction_with_current_date()
    if not hdr:
        return preamble + base
    name = (hdr.get("user_name") or "").strip()
    email = (hdr.get("user_email") or "").strip()
    uid = (hdr.get("user_id") or "").strip()
    lines: list[str] = []
    if name:
        lines.append(f"- **Name:** {name}")
    if email:
        lines.append(f"- **Email:** {email}")
    if uid:
        lines.append(f"- **User id (OAuth subject):** {uid}")
    if not lines:
        return preamble + base
    block = (
        "\n\n**Authenticated user (from the signed-in session):**\n"
        + "\n".join(lines)
        + "\n"
    )
    return preamble + base + block


root_agent = LlmAgent(
    name="master_mechanical_agent",
    # Intentional flash-lite model for cost/latency; lite models can emit function_call-only
    # turns with empty assistant text in some ADK UIs — switch to a non-lite Flash if that occurs.
    model="gemini-3.1-flash-lite-preview",
    description=(
        "HVAC and business assistant for Master Mechanical: technical HVAC help plus read-only "
        "BigQuery insights on customers, jobs, employees, and receivables (balances owed, past due) "
        f"in {BIGQUERY_DATASET_REF}. Delegates HouseCall Pro record updates to a specialized "
        "subagent with allowlisted fields and mandatory confirmation. Tone follows session "
        "(owner vs other users)."
    ),
    instruction=_instruction_with_session_identity,
    tools=[
        bigquery_toolset,
        load_artifacts_tool,
        SummarizeSpreadsheetTool(),
        AgentTool(hcp_records_agent, skip_summarization=False),
    ],
    before_model_callback=_before_model_callback,
    after_model_callback=_after_model_callback,
    before_tool_callback=_before_tool_callback,
    after_tool_callback=_after_tool_callback,
    after_agent_callback=_after_agent_callback,
    on_model_error_callback=_on_model_error_callback,
)
