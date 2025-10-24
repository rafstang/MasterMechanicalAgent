# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies
RUN uv sync --frozen

# Copy application code
COPY src/ src/

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Run the agent API server
CMD ["uv", "run", "adk", "api_server", "src/agents/MasterMechanicalAgent"]
