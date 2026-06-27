# Master Mechanical Agent

HVAC expert agent built with [Google ADK](https://github.com/google/adk-python) and BigQuery. Answers user questions about HVAC topics and can query Customer, Job, and Employee data in BigQuery (project `mastermechanical`, dataset `dev_Master_Mechanical`).

The agent emphasizes clear summaries and receivables-style questions (balances owed, past due). BigQuery usage is documented in [`src/agents/MasterMechanicalAgent/agent.py`](src/agents/MasterMechanicalAgent/agent.py): table names (`customers`, `jobs`, `job_invoices`, `job_appointments`, `employees`, `tags`, `checklists`), joins (including `employees` for technician names and contact info from job/appointment IDs), and receivables fields (`outstanding_balance`, invoice `status`, etc.), with `get_table_info` as a fallback if live metadata differs.

## Prerequisites

- **Python 3.14**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **Node.js** and npm (for the optional CopilotKit frontend in [`frontend/`](frontend/))
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
| `GOOGLE_CLOUD_PROJECT` | Optional. GCP project id for BigQuery tools (default `mastermechanical`). |
| `AGENT_TIMEZONE` | Optional. IANA timezone for the **current date/time** line appended to agent instructions (default `America/Phoenix`). Example: `UTC`. |
| `MASTER_MECHANICAL_OWNER_EMAIL` | Optional. If set to the signed-in user’s email (AG-UI / Auth.js), the assistant uses owner-oriented framing; if unset, no account is treated as the owner. |
| `HOUSECALL_PRO_API_KEY` | Required for **HouseCall Pro record updates** (field technicians updating customer/job info). MAX-plan API key; kept server-side only. BigQuery reads work without it. |
| `AG_UI_ALLOW_UNAUTHENTICATED` | **Local dev only.** Set to `true` to run the AG-UI backend without `AG_UI_INVOKER_SECRET`. Do not use in production. |
| `AG_UI_INVOKER_SECRET` | **Required in production.** Shared secret; Next.js sends it as `X-AG-UI-Token` to the FastAPI backend. |
| `AG_UI_CORS_ORIGINS` | Comma-separated browser origins allowed by the AG-UI FastAPI CORS middleware (default `http://localhost:3000`). |

See [`.env.example`](.env.example) for a full list including frontend variables.

On **Cloud Run**, BigQuery calls use the service’s **runtime service account** (unless you set a custom one), typically `PROJECT_NUMBER-compute@developer.gserviceaccount.com`. Grant that identity **`roles/bigquery.jobUser`** on the project and read access to the dataset (for example **`roles/bigquery.dataViewer`** on `dev_Master_Mechanical` or the project). Without job + data access, queries can fail or appear to hang.

This project intentionally uses **`gemini-3.1-flash-lite-preview`** for lower cost and latency. Lite models can occasionally return **function_call-only** turns with empty assistant text in some ADK UIs. If you see that in Cloud Logging (`non-text parts in the response: ['function_call']`), switch the `model` in [`agent.py`](src/agents/MasterMechanicalAgent/agent.py) to a non-lite Flash-family model (for example `gemini-3-flash-preview`).

## Run locally

Web UI (interactive chat):

```bash
uv run adk web src/agents
```

API server (e.g. for Cloud Run or local HTTP):

```bash
uv run adk api_server src/agents/MasterMechanicalAgent
```

### Custom UI (AG-UI + CopilotKit + Google sign-in)

The [Next.js](frontend/) app uses [CopilotKit](https://www.copilotkit.ai/) and the [AG-UI protocol](https://google.github.io/adk-docs/integrations/ag-ui/) to talk to a small **FastAPI** server ([`src/agents/MasterMechanicalAgent/ag_ui_app.py`](src/agents/MasterMechanicalAgent/ag_ui_app.py)) that wraps the same [`root_agent`](src/agents/MasterMechanicalAgent/agent.py). The signed-in user’s Google **subject** (`token.sub`) is sent as `X-User-Id` from the **Next.js `/api/copilotkit` route** (set server-side from Auth.js—clients cannot spoof it). The AG-UI layer maps that header into per-user ADK sessions via `user_id_extractor`.

Run **two processes** from the repo root (after `uv sync` and `cd frontend && npm install`):

**Terminal 1 — AG-UI backend (port 8000):**

```bash
uv run uvicorn src.agents.MasterMechanicalAgent.ag_ui_app:app --host 0.0.0.0 --port 8000
```

Set `AG_UI_ALLOW_UNAUTHENTICATED=true` in your `.env` for local development, or set `AG_UI_INVOKER_SECRET` and pass the same value from Next.js (see frontend env table below).

**Terminal 2 — Next.js (port 3000):**

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), sign in with Google, then use the Copilot sidebar.

**Frontend environment** (`frontend/.env.local`; see [Auth.js env names](https://authjs.dev/getting-started/installation)):

| Variable | Description |
|----------|-------------|
| `AUTH_SECRET` | Random secret for Auth.js session encryption (required in production). `NEXTAUTH_SECRET` is accepted as a fallback. |
| `AUTH_GOOGLE_ID` | Google OAuth client ID (Web application). |
| `AUTH_GOOGLE_SECRET` | Google OAuth client secret. |
| `AUTH_URL` | Optional. Base URL of the app, e.g. `http://localhost:3000` (helps OAuth redirects). |
| `AG_UI_BACKEND_URL` | URL of the FastAPI AG-UI server (default `http://localhost:8000/`). |
| `AG_UI_INVOKER_SECRET` | Optional locally; **required in production** on both Next.js and the Python backend. |

In [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials), add **Authorized redirect URI**: `http://localhost:3000/api/auth/callback/google` for the OAuth client used above.

**Backend:** `AG_UI_CORS_ORIGINS` — comma-separated allowed browser origins for the FastAPI app (default `http://localhost:3000`).

### Security checklist (CopilotKit / Cloud Run)

| Control | Purpose |
|---------|---------|
| `AG_UI_INVOKER_SECRET` on **both** services | Prevents unauthenticated POSTs to the AG-UI backend URL |
| Auth.js on Next.js | Google sign-in; identity headers set server-side only |
| `AG_UI_CORS_ORIGINS` | Restrict browser-origin calls if clients hit the backend directly |
| `MASTER_MECHANICAL_OWNER_EMAIL` | Limits “owner” framing to one verified email |
| `HOUSECALL_PRO_API_KEY` | Server-side only; required for HCP record updates (not for BigQuery reads) |
| BigQuery IAM on runtime SA | Read-only data access (`WriteMode.BLOCKED` in code) |

**Deploy scripts:** [`scripts/deploy-copilotkit-cloud-run.sh`](scripts/deploy-copilotkit-cloud-run.sh) deploys **public** Cloud Run invokers (use invoker secret). [`scripts/deploy.sh`](scripts/deploy.sh) deploys a **single IAP-protected** AG-UI service without public invoker.

Do not expose the FastAPI AG-UI URL publicly without `AG_UI_INVOKER_SECRET` or IAP in front of it.

If `uv sync` fails on Windows with “cannot access `adk.exe`”, close any process using the ADK CLI and retry.

## HouseCall Pro record updates (field technicians)

The root agent delegates customer and job **writes** to a dedicated **`hcp_records_agent`** subagent. Technicians use the same CopilotKit chat UI; no frontend changes are required.

**Requirements:** HouseCall Pro **MAX** plan with a [Public API key](https://docs.housecallpro.com/). Set `HOUSECALL_PRO_API_KEY` on the Python backend (never in the browser).

**Allowed updates (v1):**

- **Customer:** contact info (phone, email), notes, service address
- **Job:** notes, description, work status (`scheduled` / `in_progress` / `complete`), on-my-way / start / complete timestamps

**Safety:** Every write uses a two-step **propose → confirm → apply** flow. The subagent shows a before/after diff and waits for an explicit “yes” before calling the HouseCall Pro API. Server-side allowlists block pricing, scheduling, reassignment, deletes, and other sensitive fields.

**Data freshness:** Updates go to HouseCall Pro immediately. BigQuery (`dev_Master_Mechanical`) may lag until the next sync pipeline run.

### Deploy CopilotKit UI to the web (Cloud Run)

The root [**Dockerfile**](Dockerfile) runs the **AG-UI FastAPI** app (`uvicorn … ag_ui_app`). The legacy ADK built-in web UI image is [**Dockerfile.adk-web**](Dockerfile.adk-web).

**Two services** (recommended): deploy the Python API and the Next.js app separately.

1. **Secrets** (Secret Manager): ensure **`GOOGLE_API_KEY`** exists for Gemini (same secret the deploy scripts mount as `GOOGLE_GENAI_API_KEY`). **Production requires `AG_UI_INVOKER_SECRET`** on both Cloud Run services (create in Secret Manager or set as env vars). The Next.js service sends it to the Python service as `X-AG-UI-Token`.

2. **Deploy** from the repo root with bash (Git Bash / WSL / Linux/macOS):

   ```bash
   chmod +x scripts/deploy-copilotkit-cloud-run.sh
   export PROJECT_ID=mastermechanical
   export REGION=us-central1
   ./scripts/deploy-copilotkit-cloud-run.sh
   ```

   This builds from source in Cloud Build: backend uses the repo root; frontend uses [`frontend/Dockerfile`](frontend/Dockerfile) (`gcloud run deploy --source=./frontend`).

3. **Configure the frontend service** in the Cloud Run console (or `gcloud run services update`):  
   `AUTH_SECRET`, `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, **`AUTH_URL`** = your frontend HTTPS URL, **`AG_UI_BACKEND_URL`** = backend URL with a trailing slash (from `gcloud run services describe` on the backend). If you use the invoker secret, set **`AG_UI_INVOKER_SECRET`** on both services.

4. **Google OAuth**: in the Web client credentials, add **Authorized redirect URI**  
   `https://<your-frontend-host>/api/auth/callback/google`.

5. **Backend CORS** (`AG_UI_CORS_ORIGINS` on the Python service): only needed if browsers call the AG-UI URL directly; the default Next.js flow calls the backend **server-side**, so CORS is often unnecessary. Set it to your frontend origin if you add direct browser access.

**Alternative — Vercel for Next.js only:** deploy [`frontend/`](frontend/) to Vercel, set the same env vars there, and point **`AG_UI_BACKEND_URL`** at your Cloud Run AG-UI URL. Keep **`AG_UI_INVOKER_SECRET`** aligned if you enable it.

## Tests

```bash
uv run pytest tests/ -v
```

## Deploy to Cloud Run

There are two supported paths; both build container images in **Cloud Build** from the repo (no local Docker required).

| Goal | Script | What it deploys |
|------|--------|-----------------|
| **CopilotKit (Next.js + AG-UI)** | [`scripts/deploy-copilotkit-cloud-run.sh`](scripts/deploy-copilotkit-cloud-run.sh) | Backend from repo root [Dockerfile](Dockerfile) (`ag_ui_app`) + frontend from [`frontend/Dockerfile`](frontend/Dockerfile). See [Deploy CopilotKit UI to the web](#deploy-copilotkit-ui-to-the-web-cloud-run) above for env vars. |
| **Single AG-UI service + IAP** | [`scripts/deploy.sh`](scripts/deploy.sh) | One Cloud Run service from the same root Dockerfile, **no** public invoker, [IAP](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run) enabled, Gemini key from Secret Manager `GOOGLE_API_KEY`. |

Defaults and overrides are documented at the top of each script (`PROJECT_ID`, `REGION`, service names). Get a service URL after deploy:

```bash
gcloud run services describe SERVICE_NAME --region=REGION --project=PROJECT_ID --format='value(status.url)'
```

### `deploy.sh` (IAP single service)

Run from the repo root (bash: Git Bash, WSL, Linux, macOS):

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

Edit **`AUTHORIZED_USERS`** in [`scripts/deploy.sh`](scripts/deploy.sh) to list Google accounts that should receive **`roles/run.invoker`** on that service. Grant those same accounts the IAP **Web App User** role (`roles/iap.httpsResourceAccessor`) so they can sign in through IAP. Secret Manager must contain **`GOOGLE_API_KEY`** (Gemini), as in the CopilotKit flow.

The default service name is **`mastermechanical-ag-ui-iap`** (override with `SERVICE_NAME`) so it does not collide with the CopilotKit backend default **`mastermechanical-ag-ui`** if you use both.

### IAP custom OAuth (fix "Empty Google Account OAuth client ID(s)/secret(s)")

Projects not in an organization often need a **custom OAuth client** for IAP. Inspect settings:

```bash
./scripts/check-iap-settings.sh
```

If the IAP OAuth client is missing, create a **Web application** OAuth client in [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials), add the IAP redirect URI (see Google’s IAP docs for the exact URL pattern), then apply it with [`scripts/set-iap-oauth.sh`](scripts/set-iap-oauth.sh) or `gcloud iap settings set` using **`--service=YOUR_CLOUD_RUN_SERVICE_NAME`** and your region/project.

After IAP works, open the service **root URL** from `gcloud run services describe` (chat UI for the AG-UI app; OpenAPI docs are typically at `/docs` on the same host).
