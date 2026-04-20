#!/usr/bin/env bash
# Deploy a single AG-UI (FastAPI) service to Cloud Run with IAP and per-user IAM invokers.
# Builds from the repo root Dockerfile (same image as CopilotKit backend: uvicorn ag_ui_app).
#
# Prerequisites: gcloud auth, Secret Manager secret GOOGLE_API_KEY (mounted as GOOGLE_GENAI_API_KEY).
#
# Configure:
#   export PROJECT_ID=mastermechanical
#   export REGION=us-central1
#   export SERVICE_NAME=mastermechanical-ag-ui-iap   # avoid clashing with CopilotKit backend name if both exist
#   export PROJECT_NUMBER=123456789012             # gcloud projects describe $PROJECT_ID --format='value(projectNumber)'
#
# Edit AUTHORIZED_USERS below (Google accounts that may invoke the service via IAP).

set -euo pipefail

# Accounts to grant roles/run.invoker (add/remove as needed).
AUTHORIZED_USERS=(
)

SERVICE_NAME="${SERVICE_NAME:-mastermechanical-ag-ui-iap}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${PROJECT_ID:-mastermechanical}"
PROJECT_NUMBER="${PROJECT_NUMBER:-}"
if [[ -z "${PROJECT_NUMBER}" ]]; then
  PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
fi
IAP_SA="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "Deploying ${SERVICE_NAME} (AG-UI FastAPI) to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --source=. \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --memory=1Gi \
  --no-allow-unauthenticated \
  --quiet

echo "Configuring environment variables..."
gcloud run services update "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}" \
  --update-secrets=GOOGLE_GENAI_API_KEY=GOOGLE_API_KEY:latest

echo "Configuring IAM: authorized users only..."
gcloud run services remove-iam-policy-binding "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --member=allUsers \
  --role=roles/run.invoker \
  --quiet 2>/dev/null || true

gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --member="${IAP_SA}" \
  --role=roles/run.invoker \
  --quiet

for email in "${AUTHORIZED_USERS[@]}"; do
  gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="user:${email}" \
    --role=roles/run.invoker \
    --quiet
done

echo "Enabling IAP for browser sign-in..."
gcloud beta run services update "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --iap \
  --quiet

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"
echo ""
echo "Deployment complete."
echo "Service URL: ${SERVICE_URL}"
echo ""
if [[ ${#AUTHORIZED_USERS[@]} -gt 0 ]]; then
  echo "Cloud Run invoker granted to:"
  for email in "${AUTHORIZED_USERS[@]}"; do
    echo "  - ${email}"
  done
else
  echo "AUTHORIZED_USERS is empty — add Google accounts to the array in this script, then re-run IAM steps or add bindings manually."
fi
