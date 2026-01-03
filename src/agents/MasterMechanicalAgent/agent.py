import os

from google.adk.agents.llm_agent import LlmAgent
from google.adk.auth.auth_credential import AuthCredentialTypes
from google.adk.tools.bigquery.bigquery_credentials import BigQueryCredentialsConfig
from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig
from google.adk.tools.bigquery.config import WriteMode
import google.auth

# Define an appropriate credential type
CREDENTIALS_TYPE = AuthCredentialTypes.SERVICE_ACCOUNT

# Write modes define BigQuery access control of agent:
# ALLOWED: Tools will have full write capabilites.
# BLOCKED: Default mode. Effectively makes the tool read-only.
# PROTECTED: Only allows writes on temporary data for a given BigQuery session.

tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

if CREDENTIALS_TYPE == AuthCredentialTypes.OAUTH2:
  # Initiaze the tools to do interactive OAuth
  credentials_config = BigQueryCredentialsConfig(
      client_id=os.getenv("OAUTH_CLIENT_ID"),
      client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
  )
elif CREDENTIALS_TYPE == AuthCredentialTypes.SERVICE_ACCOUNT:
  # Initialize the tools to use the credentials in the service account key.
  creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
  if creds_file and os.path.exists(creds_file):
    creds, _ = google.auth.load_credentials_from_file(creds_file)
    credentials_config = BigQueryCredentialsConfig(credentials=creds)
  else:
    # Fallback to application default credentials
    application_default_credentials, _ = google.auth.default()
    credentials_config = BigQueryCredentialsConfig(
        credentials=application_default_credentials
    )
else:
  # Initialize the tools to use the application default credentials.
  application_default_credentials, _ = google.auth.default()
  credentials_config = BigQueryCredentialsConfig(
      credentials=application_default_credentials
  )

bigquery_toolset = BigQueryToolset(credentials_config=credentials_config,   tool_filter=[
'list_dataset_ids','get_dataset_info','list_table_ids','get_table_info','execute_sql',])

root_agent = LlmAgent(
    name="weather_time_agent",
    model="gemini-2.5-flash",
    description=("Agent to answer HVAC questions."),
    instruction="""
      You are a helpful HVAC expert who can answer user questions about HVAC topics using your tools."
      When asked about data or the database, use your bigquery_toolset tools to automatically query 
      Customer and Job information in the following database:
        projectid: mastermechanical
        dataset: dev_Master_Mechanical""",
    tools=[bigquery_toolset],
)