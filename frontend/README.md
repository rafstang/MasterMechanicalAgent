# Master Mechanical — Next.js frontend

CopilotKit chat UI with Google sign-in (Auth.js). Talks to the Python AG-UI backend on port **8000** while this app runs on port **3000**.

**Setup, environment variables, OAuth, and deployment** are documented in the [root README](../README.md) and [`.env.example`](../.env.example).

## Quick start

```bash
cd frontend
npm install
npm run dev
```

Ensure the AG-UI backend is running (`uv run uvicorn src.agents.MasterMechanicalAgent.ag_ui_app:app --port 8000` from repo root) with `AG_UI_ALLOW_UNAUTHENTICATED=true` or matching `AG_UI_INVOKER_SECRET`.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Local dev server (port 3000) |
| `npm run lint` | ESLint |
| `npm run build` | Production build |
