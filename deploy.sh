#!/bin/bash
# Deployment script for MasterMechanicalAgent to Google Cloud Run

# List of authorized user emails - add/remove as needed
AUTHORIZED_USERS=(
  "jake.slade@gmail.com"
  "rafstang@gmail.com"
)

SERVICE_NAME="adk-default-service-name"
REGION="us-central1"

echo "Deploying MasterMechanicalAgent to Cloud Run..."

# Deploy using ADK
uv run adk deploy cloud_run --with_ui src/agents/MasterMechanicalAgent

# Update environment variables
echo "Configuring environment variables..."
gcloud run services update $SERVICE_NAME \
  --region=$REGION \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=mastermechanical,GOOGLE_CLOUD_LOCATION=us-central1" \
  --update-secrets=GOOGLE_GENAI_API_KEY=API_KEY:latest

# Allow public access
echo "Allowing public access..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
  --region=$REGION \
  --member=allUsers \
  --role=roles/run.invoker \
  --quiet 2>/dev/null || true

echo "Deployment complete!"
echo "Service URL: https://adk-default-service-name-133058664187.us-central1.run.app"
echo ""
echo "Authorized users:"
for email in "${AUTHORIZED_USERS[@]}"; do
  echo "  - $email"
done
