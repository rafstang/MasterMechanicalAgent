#!/bin/bash
# Apply custom OAuth client to IAP for the Cloud Run service (CLI only).
# The OAuth client itself must be created in the Console:
#   APIs & Services → Credentials → Create OAuth 2.0 Client ID (Web application)
#   Add redirect URI: https://iap.googleapis.com/v1/oauth/clientIds/YOUR_CLIENT_ID:handleRedirect
#
# Usage:
#   export IAP_OAUTH_CLIENT_ID="123...apps.googleusercontent.com"
#   export IAP_OAUTH_CLIENT_SECRET="GOCSPX-..."
#   ./scripts/set-iap-oauth.sh

set -e

PROJECT_ID="mastermechanical"
REGION="us-central1"
SERVICE_NAME="adk-default-service-name"

if [ -z "$IAP_OAUTH_CLIENT_ID" ] || [ -z "$IAP_OAUTH_CLIENT_SECRET" ]; then
  echo "Error: set IAP_OAUTH_CLIENT_ID and IAP_OAUTH_CLIENT_SECRET in the environment."
  echo "Example:"
  echo "  export IAP_OAUTH_CLIENT_ID=\"YOUR_CLIENT_ID.apps.googleusercontent.com\""
  echo "  export IAP_OAUTH_CLIENT_SECRET=\"GOCSPX-...\""
  echo "  ./scripts/set-iap-oauth.sh"
  exit 1
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

cat << EOF > "$TMP"
accessSettings:
  oauthSettings:
    clientId: $IAP_OAUTH_CLIENT_ID
    clientSecret: $IAP_OAUTH_CLIENT_SECRET
EOF

echo "Applying OAuth client to IAP for $SERVICE_NAME..."
gcloud iap settings set "$TMP" \
  --project="$PROJECT_ID" \
  --resource-type=cloud-run \
  --region="$REGION" \
  --service="$SERVICE_NAME"

echo "Done. Run ./scripts/check-iap-settings.sh to verify; then open the service URL."
