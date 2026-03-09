# Master Mechanical Agent

HVAC expert agent built with [Google ADK](https://github.com/google/adk-python) and BigQuery. Answers user questions about HVAC topics and can query Customer and Job data in BigQuery (project `mastermechanical`, dataset `dev_Master_Mechanical`).

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

Ensure Secret Manager has a secret named `API_KEY` with your Gemini API key, and that the script’s `SERVICE_NAME` / `REGION` match your project. The script also sets IAM so the service is publicly invokable. For the full ADK build/deploy step to succeed, run from the devcontainer or Linux (on Windows the script may still update env vars and IAM on an existing service).
