#!/bin/bash
# Deployment script for MasterMechanicalAgent to Google Cloud Run

# List of authorized user emails - add/remove as needed
AUTHORIZED_USERS=(
  "Jake.Slade@mastermechanicalaz.com"
  "rafstang@gmail.com"
  "alberto.nieto.80@gmail.com"
)

SERVICE_NAME="adk-default-service-name"
REGION="us-central1"
PROJECT_ID="mastermechanical"
# IAP service agent needs invoker so IAP can call Cloud Run (project number, not ID).
PROJECT_NUMBER="133058664187"
IAP_SA="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"

echo "Deploying MasterMechanicalAgent to Cloud Run..."

# On Windows, ADK deploy fails with WinError 2. Use gcloud run deploy --source so Cloud Build
# builds the image in the cloud from the repo Dockerfile (no local Docker needed).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
USE_SOURCE_DEPLOY=false
if [ -n "$WINDIR" ] || [ "$(uname -o 2>/dev/null)" = "Msys" ]; then
  USE_SOURCE_DEPLOY=true
fi
if [ "$USE_SOURCE_DEPLOY" = true ]; then
  echo "Using gcloud run deploy --source (Windows)..."
  cd "$REPO_ROOT"
  gcloud run deploy $SERVICE_NAME \
    --source=. \
    --region=$REGION \
    --project=$PROJECT_ID \
    --memory=1Gi \
    --no-allow-unauthenticated \
    --quiet
else
  uv run adk deploy cloud_run --with_ui src/agents/MasterMechanicalAgent
fi

# Update environment variables
echo "Configuring environment variables..."
gcloud run services update $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}" \
  --update-secrets=GOOGLE_GENAI_API_KEY=API_KEY:latest

# Restrict access to authorized users only (remove public invoker if present)
echo "Configuring IAM: authorized users only..."
gcloud run services remove-iam-policy-binding $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --member=allUsers \
  --role=roles/run.invoker \
  --quiet 2>/dev/null || true

# IAP service agent must have invoker so browser sign-in works.
gcloud run services add-iam-policy-binding $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --member="$IAP_SA" \
  --role=roles/run.invoker \
  --quiet

for email in "${AUTHORIZED_USERS[@]}"; do
  gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --region=$REGION \
    --project=$PROJECT_ID \
    --member="user:${email}" \
    --role=roles/run.invoker \
    --quiet
done

# Re-enable IAP (gcloud run deploy --source does not set it, so each deploy can leave IAP off).
echo "Enabling IAP for browser sign-in..."
gcloud beta run services update $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --iap \
  --quiet

echo "Deployment complete!"
echo "Service URL: https://adk-default-service-name-133058664187.us-central1.run.app"
echo ""
echo "Authorized users:"
for email in "${AUTHORIZED_USERS[@]}"; do
  echo "  - $email"
done
