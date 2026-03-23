import os
from datetime import datetime, timezone
from pathlib import Path
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
from google.adk.auth.auth_credential import AuthCredentialTypes
from google.adk.tools.bigquery.bigquery_credentials import BigQueryCredentialsConfig
from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig
from google.adk.tools.bigquery.config import WriteMode
import google.auth

# Define an appropriate credential type
CREDENTIALS_TYPE = AuthCredentialTypes.SERVICE_ACCOUNT

# Write modes define BigQuery access control of agent:
# ALLOWED: Tools will have full write capabilites.
# BLOCKED: Default mode. Effectively makes the tool read-only.
# PROTECTED: Only allows writes on temporary data for a given BigQuery session.

tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

if CREDENTIALS_TYPE == AuthCredentialTypes.OAUTH2:
  # Initiaze the tools to do interactive OAuth
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

_AGENT_INSTRUCTION = """
You are the Master Mechanical HVAC assistant. Your primary user is the HVAC company owner (business
decisions, not a field-install manual). Give clear, concise answers: totals, ranked lists, and short
summaries they can act on.

**HVAC:** Answer technical HVAC questions from your expertise when no database is needed.

**BigQuery:** You have read-only tools. Use them when the owner asks about customers, jobs,
scheduling, invoices, or money owed (balances, past due, who owes the most).

**Dataset:** `mastermechanical.dev_Master_Mechanical`. Always use fully qualified table names:
`mastermechanical.dev_Master_Mechanical.<table>`.

**Ignore staging tables:** Do not query tables whose names end with `_staging` (for example
`customers_staging`, `jobs_staging`) unless the user explicitly asks for staging or pipeline/debug
data. Use the canonical tables: `customers`, `jobs`, `job_invoices`, `job_appointments`, `tags`,
`checklists`, and `sync_metadata` when relevant.

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

- `tags` — id, name, created_at (STRING), updated_at (STRING); lookup / label list.

- `checklists` — id (required), title, job_uuid, estimate_uuid; nested repeated `sections` with
  `items` (type, title, required, comment, value, order_index). Relate to jobs via job_uuid when ids match.

- `sync_metadata` — pipeline status per upstream table: `table_name`, `last_sync_timestamp` (TIMESTAMP),
  `last_sync_status`, `records_synced`, `records_skipped`, `sync_duration_seconds`, `error_message`.
  Use for “when was X last synced?”, load health, or recent sync errors—not for customer AR math.

**Receivables / owner-focused queries:**
- Primary AR signal on the job: `jobs.outstanding_balance` and `jobs.total_amount`.
- Invoice rollups: `job_invoices.total`, `job_invoices.status`, `job_invoices.invoice_number`.
- There is no dedicated "due date" column in this snapshot; for "past due" or aging, combine status
  fields with `created_at` / `updated_at` on jobs or invoices, or schedule dates, and state
  assumptions clearly to the owner.
- Rank "who owes the most": aggregate `SUM(jobs.outstanding_balance)` (or invoice totals) grouped
  by customer via `jobs.customer.id` joined to `customers`.

**Reporting money:** Assume USD unless data says otherwise. Include customer name/id and job or
invoice_number when present.

Other tools: `list_dataset_ids`, `get_dataset_info`, `list_table_ids` if you need to verify names.
"""


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


root_agent = LlmAgent(
    name="master_mechanical_agent",
    # Prefer a non-lite Flash-family model so tool/function calling stays reliable with ADK;
    # flash-lite + function_call-only turns can surface as empty text in the UI (see README).
    model="gemini-3-flash-preview",
    description=(
        "HVAC and business assistant for the company owner: technical HVAC help plus read-only "
        "BigQuery insights on customers, jobs, and receivables (balances owed, past due) in "
        "mastermechanical.dev_Master_Mechanical."
    ),
    instruction=_instruction_with_current_date(),
    tools=[bigquery_toolset],
)