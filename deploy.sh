#!/bin/bash
# Deployment script for MasterMechanicalAgent to Google Cloud Run

echo "Deploying MasterMechanicalAgent to Cloud Run..."

# Deploy using ADK
uv run adk deploy cloud_run --with_ui src/agents/MasterMechanicalAgent

# Update environment variables
echo "Configuring environment variables..."
gcloud run services update adk-default-service-name \
  --region=us-central1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=mastermechanical,GOOGLE_CLOUD_LOCATION=us-central1" \
  --update-secrets=GOOGLE_GENAI_API_KEY=API_KEY:latest

echo "Deployment complete!"
echo "Service URL: https://adk-default-service-name-133058664187.us-central1.run.app"
