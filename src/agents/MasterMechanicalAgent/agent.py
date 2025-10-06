from google.adk.agents import Agent

root_agent = Agent(
    name="weather_time_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to answer HVAC questions."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about HVAC topics."
    ),
)