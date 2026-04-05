#!/usr/bin/env bash
# Check IAP and OAuth-related settings for the Cloud Run agent (CLI only).
# Usage: ./scripts/check-iap-settings.sh
# Optional: export PROJECT_ID, REGION, SERVICE_NAME (default matches scripts/deploy.sh).

PROJECT_ID="${PROJECT_ID:-mastermechanical}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-mastermechanical-ag-ui-iap}"

echo "=== 1. Cloud Run service: IAP enabled? ==="
gcloud beta run services describe $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="yaml(spec.template.metadata.annotations)" 2>/dev/null | grep -i iap || echo "(no IAP annotation or not found)"

echo ""
echo "=== 2. IAP settings for this Cloud Run service (OAuth client is here if set) ==="
gcloud iap settings get \
  --project=$PROJECT_ID \
  --resource-type=cloud-run \
  --region=$REGION \
  --service=$SERVICE_NAME 2>&1

echo ""
echo "=== 3. Cloud Run IAM: who has run.invoker? ==="
gcloud run services get-iam-policy $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="table(bindings.role,bindings.members)" 2>&1

echo ""
echo "=== 4. IAP access policy (who can sign in via IAP) ==="
gcloud beta iap web get-iam-policy \
  --project=$PROJECT_ID \
  --resource-type=cloud-run \
  --region=$REGION \
  --service=$SERVICE_NAME 2>&1

echo ""
echo "If 'oauthSettings' / clientId is missing in section 2, you must set a custom OAuth client."
echo "See README or: Create OAuth client in Console (APIs & Services -> Credentials -> Create OAuth 2.0 Client ID, Web application),"
echo "then: gcloud iap settings set iap-oauth.yaml --project=$PROJECT_ID --resource-type=cloud-run --region=$REGION --service=$SERVICE_NAME"
echo "with iap-oauth.yaml containing: accessSettings.oauthSettings.clientId and clientSecret"
