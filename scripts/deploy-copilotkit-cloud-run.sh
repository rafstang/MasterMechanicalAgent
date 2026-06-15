#!/usr/bin/env bash
# Deploy CopilotKit stack to Google Cloud Run: AG-UI FastAPI (repo root) + Next.js (frontend/).
# Prerequisites: gcloud auth, project set, Secret Manager secret GOOGLE_API_KEY (Gemini), optional AG_UI_INVOKER secret.
#
# For a single AG-UI service with IAP and no public invoker, use scripts/deploy.sh instead.
#
# Usage (from repo root, bash):
#   chmod +x scripts/deploy-copilotkit-cloud-run.sh
#   export PROJECT_ID=mastermechanical
#   export REGION=us-central1
#   # Optional: export BACKEND_SERVICE, FRONTEND_SERVICE
#   ./scripts/deploy-copilotkit-cloud-run.sh
#
# After deploy, set Next.js service env in Cloud Run console (or gcloud run services update):
#   AUTH_SECRET, AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET, AUTH_URL, AG_UI_BACKEND_URL, AG_UI_INVOKER_SECRET

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-mastermechanical}"
REGION="${REGION:-us-central1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-mastermechanical-ag-ui}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-mastermechanical-web}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Deploy AG-UI backend: $BACKEND_SERVICE ==="
gcloud run deploy "$BACKEND_SERVICE" \
  --source=. \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --memory=1Gi \
  --allow-unauthenticated \
  --quiet

gcloud run services update "$BACKEND_SERVICE" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}" \
  --update-secrets=GOOGLE_GENAI_API_KEY=GOOGLE_API_KEY:latest \
  --quiet

BACKEND_URL="$(gcloud run services describe "$BACKEND_SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')"
echo "Backend URL: $BACKEND_URL"

echo ""
echo "=== Deploy Next.js frontend: $FRONTEND_SERVICE ==="
gcloud run deploy "$FRONTEND_SERVICE" \
  --source=./frontend \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --memory=512Mi \
  --allow-unauthenticated \
  --quiet

FRONTEND_URL="$(gcloud run services describe "$FRONTEND_SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')"
echo "Frontend URL: $FRONTEND_URL"

echo ""
echo "=== Next: configure frontend environment variables ==="
echo "In Cloud Run console for $FRONTEND_SERVICE, set:"
echo "  AUTH_SECRET           (random secret)"
echo "  AUTH_GOOGLE_ID        (OAuth Web client ID)"
echo "  AUTH_GOOGLE_SECRET    (from Secret Manager or env)"
echo "  AUTH_URL              $FRONTEND_URL"
echo "  AG_UI_BACKEND_URL     ${BACKEND_URL}/"
echo "Required for production security (set same value on both services):"
echo "  AG_UI_INVOKER_SECRET  (Secret Manager secret AG_UI_INVOKER recommended)"
echo "Do NOT set AG_UI_ALLOW_UNAUTHENTICATED on Cloud Run."
echo ""
echo "Google OAuth: add Authorized redirect URI:"
echo "  ${FRONTEND_URL}/api/auth/callback/google"
echo ""
echo "Backend CORS (if browser calls AG-UI directly): set AG_UI_CORS_ORIGINS on $BACKEND_SERVICE to $FRONTEND_URL"
