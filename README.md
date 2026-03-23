# Master Mechanical Agent

HVAC expert agent built with [Google ADK](https://github.com/google/adk-python) and BigQuery. Answers user questions about HVAC topics and can query Customer and Job data in BigQuery (project `mastermechanical`, dataset `dev_Master_Mechanical`).

The agent is aimed at the **business owner**: it emphasizes clear summaries and receivables-style questions (balances owed, past due). BigQuery usage is documented in [`src/agents/MasterMechanicalAgent/agent.py`](src/agents/MasterMechanicalAgent/agent.py): table names (`customers`, `jobs`, `job_invoices`, `job_appointments`, `tags`, `checklists`), joins, and receivables fields (`outstanding_balance`, invoice `status`, etc.), with `get_table_info` as a fallback if live metadata differs.

## Prerequisites

- **Python 3.14**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- Optional: GCP/BigQuery credentials for database tools

## Setup

```bash
git clone <repo-url>
cd MasterMechanicalAgent
uv sync
```

## Environment

Configure via environment variables or a `.env` file in `src/agents/MasterMechanicalAgent/` (or project root).

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Required for the Gemini model. The agent also checks `GOOGLE_GENAI_API_KEY` and copies it to `GOOGLE_API_KEY` if set. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a GCP service account key JSON for BigQuery. If unset, application default credentials are used. |
| `AGENT_TIMEZONE` | Optional. IANA timezone for the **current date/time** line appended to agent instructions (default `America/Phoenix`). Example: `UTC`. |

On **Cloud Run**, BigQuery calls use the service’s **runtime service account** (unless you set a custom one), typically `PROJECT_NUMBER-compute@developer.gserviceaccount.com`. Grant that identity **`roles/bigquery.jobUser`** on the project and read access to the dataset (for example **`roles/bigquery.dataViewer`** on `dev_Master_Mechanical` or the project). Without job + data access, queries can fail or appear to hang.

If Cloud Logging shows `non-text parts in the response: ['function_call']` and the dev UI shows **no assistant text after a tool runs**, that often comes from using **`gemini-2.5-flash-lite`** (or similar lite models) with tools. This project uses **`gemini-3-flash-preview`** for more reliable function calling with the ADK.

## Run locally

Web UI (interactive chat):

```bash
uv run adk web src/agents
```

API server (e.g. for Cloud Run or local HTTP):

```bash
uv run adk api_server src/agents/MasterMechanicalAgent
```

## Tests

```bash
uv run pytest tests/ -v
```

## Deploy to Cloud Run

**[deploy.sh](deploy.sh)** uses the ADK’s built-in Cloud Run deploy with the web UI and pulls the Gemini API key from GCP Secret Manager (`API_KEY`).

```bash
./deploy.sh
```

Ensure Secret Manager has a secret named `API_KEY` with your Gemini API key, and that the script’s `SERVICE_NAME` / `REGION` match your project. On Windows, the script uses `gcloud run deploy --source .` so the image is built in Cloud Build from the repo [Dockerfile](Dockerfile) (no local Docker required). On Linux/macOS it uses `adk deploy cloud_run --with_ui`.

### Access control

The service **requires authentication**. Only the users listed in `AUTHORIZED_USERS` in [scripts/deploy.sh](scripts/deploy.sh) are granted the Cloud Run Invoker role and can invoke the service. Direct browser visits to the service URL return **403** unless the request includes a valid identity (e.g. via [Identity-Aware Proxy (IAP) for Cloud Run](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run) or a client that sends a user identity token). For browser-based sign-in with Google, enable IAP for the Cloud Run service and grant the same users the IAP "Web App User" role (`roles/iap.httpsResourceAccessor`).

#### IAP custom OAuth (fix "Empty Google Account OAuth client ID(s)/secret(s)")

Projects not in an organization must use a **custom OAuth client**. Check current IAP settings from the CLI:

```bash
./scripts/check-iap-settings.sh
```

If section 2 shows no `oauthSettings` / `clientId`, do the following.

1. **Create an OAuth 2.0 client** in the console: [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials?project=mastermechanical) → **Create Credentials** → **OAuth 2.0 Client ID**. Application type: **Web application**. Add this **Authorized redirect URI** (replace `YOUR_CLIENT_ID` with the new client ID after creation, or use a placeholder and edit after):
   ```
   https://iap.googleapis.com/v1/oauth/clientIds/YOUR_CLIENT_ID:handleRedirect
   ```
   Copy the **Client ID** and **Client secret**.

2. **Apply the client to IAP** via CLI (no secret file; use env vars):

   ```bash
   export IAP_OAUTH_CLIENT_ID="YOUR_CLIENT_ID.apps.googleusercontent.com"
   export IAP_OAUTH_CLIENT_SECRET="GOCSPX-..."
   ./scripts/set-iap-oauth.sh
   ```

   Alternatively, create `iap-oauth.yaml` with the same `accessSettings.oauthSettings` and run:

   ```bash
   gcloud iap settings set iap-oauth.yaml --project=mastermechanical --resource-type=cloud-run --region=us-central1 --service=adk-default-service-name
   ```

   Reload the service URL; you should get a Google sign-in page.

#### Service URL and paths

After signing in via IAP, use the **root URL** for the built-in ADK web UI (chat, sessions, state):

- **Web UI:** [https://adk-default-service-name-133058664187.us-central1.run.app](https://adk-default-service-name-133058664187.us-central1.run.app)
- **Interactive API (Swagger):** [https://adk-default-service-name-133058664187.us-central1.run.app/docs](https://adk-default-service-name-133058664187.us-central1.run.app/docs)
