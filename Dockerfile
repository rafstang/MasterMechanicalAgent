# Build and run MasterMechanicalAgent on Cloud Run (no local Docker required;
# use: gcloud run deploy --source .)
# Python 3.14 to match project requires-python.
FROM python:3.14-slim

WORKDIR /app

# Install uv for fast, reproducible installs.
RUN apt-get update -y && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh && mv /root/.local/bin/uv /usr/local/bin/ \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests and sync (no dev deps).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy agent and app source.
COPY src ./src

# Cloud Run sets PORT; default 8080. Bind to 0.0.0.0 for external traffic.
ENV PORT=8080
EXPOSE 8080

# ADK web server (API + built-in web UI). Agents dir is the parent of MasterMechanicalAgent.
CMD ["sh", "-c", "uv run adk web src/agents --port ${PORT} --host 0.0.0.0 --no-reload"]
