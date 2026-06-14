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
from google.adk.auth.auth_credential import AuthCredentialTypes
from google.genai import types
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.bigquery.bigquery_credentials import BigQueryCredentialsConfig
from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
from google.genai.errors import APIError as GenaiAPIError
import google.auth

logger = logging.getLogger(__name__)

# Define an appropriate credential type
CREDENTIALS_TYPE = AuthCredentialTypes.SERVICE_ACCOUNT

# Write modes define BigQuery access control of agent:
# ALLOWED: Tools will have full write capabilities.
# BLOCKED: Default mode. Effectively makes the tool read-only.
# PROTECTED: Only allows writes on temporary data for a given BigQuery session.

tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

if CREDENTIALS_TYPE == AuthCredentialTypes.OAUTH2:
    # Initialize the tools to do interactive OAuth
    credentials_config = BigQueryCredentialsConfig(
        client_id=os.getenv("OAUTH_CLIENT_ID"),
        client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
    )
elif CREDENTIALS_TYPE == AuthCredentialTypes.SERVICE_ACCOUNT:
    # Initialize the tools to use the credentials in the service account key.
    creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_file and os.path.exists(creds_file):
        creds, _ = google.auth.load_credentials_from_file(creds_file)
        credentials_config = BigQueryCredentialsConfig(credentials=creds)
    else:
        # Fallback to application default credentials
        application_default_credentials, _ = google.auth.default()
        credentials_config = BigQueryCredentialsConfig(
            credentials=application_default_credentials
        )
else:
    # Initialize the tools to use the application default credentials.
    application_default_credentials, _ = google.auth.default()
    credentials_config = BigQueryCredentialsConfig(
        credentials=application_default_credentials
    )

bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config,
    bigquery_tool_config=tool_config,
    tool_filter=[
        "list_dataset_ids",
        "get_dataset_info",
        "list_table_ids",
        "get_table_info",
        "execute_sql",
    ],
)

# Web UI: only this signed-in email gets "owner" tone. Set MASTER_MECHANICAL_OWNER_EMAIL in env
# (e.g. Cloud Run, .env); leave unset to disable owner-specific framing for everyone.
_OWNER_EMAIL = (os.environ.get("MASTER_MECHANICAL_OWNER_EMAIL") or "").strip().lower()

_AGENT_INSTRUCTION = """
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
`mastermechanical.dev_Master_Mechanical.employees` with a case-insensitive match on `email`.
Clearly distinguish:
- **OAuth subject** (signed-in identity; shown as User id in the session block)
- **Employee / business ID** from `employees.id` (the Field Service / Pro ID used on jobs)

Do **not** use `customers` to look up staff; staff live in `employees`. If no employee row matches
the session email, say so and offer to search by name if they provide it.

**HVAC:** Answer technical HVAC questions from your expertise when no database is needed.

**BigQuery:** You have read-only tools. Use them when the user asks about customers, jobs,
employees or technicians, scheduling, invoices, or money owed (balances, past due, who owes the most).

**Dataset:** `mastermechanical.dev_Master_Mechanical`. Always use fully qualified table names:
`mastermechanical.dev_Master_Mechanical.<table>`.

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
- There is no dedicated "due date" column in this snapshot; for "past due" or aging, combine status
  fields with `created_at` / `updated_at` on jobs or invoices, or schedule dates, and state
  assumptions clearly.
- Rank "who owes the most": aggregate `SUM(jobs.outstanding_balance)` (or invoice totals) grouped
  by customer via `jobs.customer.id` joined to `customers`.

**Reporting money:** Assume USD unless data says otherwise. Include customer name/id and job or
invoice_number when present.

**Technician / employee reporting:** Prefer `employees` for display: use `COALESCE(NULLIF(TRIM(name), ''),
  TRIM(CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, ''))))` (or equivalent) for a
  readable label, then show `employees.id` in parentheses. If an ID from a job or appointment has no
  matching `employees` row, label it **unmatched employee ID**—do not claim the dataset lacks names
  globally.

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
    del args
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
    # Prefer a non-lite Flash-family model so tool/function calling stays reliable with ADK;
    # flash-lite + function_call-only turns can surface as empty text in the UI (see README).
    model="gemini-3.1-flash-lite-preview",
    description=(
        "HVAC and business assistant for Master Mechanical: technical HVAC help plus read-only "
        "BigQuery insights on customers, jobs, employees, and receivables (balances owed, past due) "
        "in mastermechanical.dev_Master_Mechanical. Tone follows session (owner vs other users)."
    ),
    instruction=_instruction_with_session_identity,
    tools=[bigquery_toolset],
    before_model_callback=_before_model_callback,
    after_model_callback=_after_model_callback,
    before_tool_callback=_before_tool_callback,
    after_tool_callback=_after_tool_callback,
    after_agent_callback=_after_agent_callback,
    on_model_error_callback=_on_model_error_callback,
)
