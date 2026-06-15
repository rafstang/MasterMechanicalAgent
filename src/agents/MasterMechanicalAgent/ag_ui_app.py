"""FastAPI app exposing the Master Mechanical ADK agent via AG-UI (for CopilotKit + HttpAgent)."""

from __future__ import annotations

import os
import secrets
from typing import Any

from ag_ui.core import RunAgentInput
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.adk.apps import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from starlette.requests import Request

# Importing the agent loads project `.env` and maps GOOGLE_GENAI_API_KEY → GOOGLE_API_KEY (see agent.py).
from src.agents.MasterMechanicalAgent.agent import root_agent  # noqa: E402

# Headers the Next.js `/api/copilotkit` route sets from Auth.js (must not be overridden by client body).
_IDENTITY_HEADER_NAMES = ("x-user-id", "x-user-email", "x-user-name")

_CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]
_CORS_ALLOW_HEADERS = [
    "Content-Type",
    "Authorization",
    "X-AG-UI-Token",
    "X-User-Id",
    "X-User-Email",
    "X-User-Name",
]


def _allow_unauthenticated() -> bool:
    return os.getenv("AG_UI_ALLOW_UNAUTHENTICATED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _validate_invoker_config() -> None:
    if _allow_unauthenticated():
        return
    if not os.getenv("AG_UI_INVOKER_SECRET"):
        raise RuntimeError(
            "AG_UI_INVOKER_SECRET must be set when AG_UI_ALLOW_UNAUTHENTICATED is not true. "
            "For local development only, set AG_UI_ALLOW_UNAUTHENTICATED=true."
        )


_validate_invoker_config()

mastermechanical_app = App(
    name="mastermechanical",
    root_agent=root_agent,
    plugins=[SaveFilesAsArtifactsPlugin()],
)


def _http_header_to_state_key(header_name: str) -> str:
    key = header_name.lower()
    if key.startswith("x-"):
        key = key[2:]
    return key.replace("-", "_")


_IDENTITY_STATE_KEYS = frozenset(_http_header_to_state_key(h) for h in _IDENTITY_HEADER_NAMES)


async def _extract_trusted_identity_headers(
    request: Request, input_data: RunAgentInput
) -> dict[str, Any]:
    """Merge state.headers so CopilotKit request body cannot spoof identity over HTTP headers.

    ag_ui_adk's default extractor lets existing client state override incoming headers; that can
    leave a stale `user_email` and wrong owner/session behavior.
    """
    server: dict[str, str] = {}
    for name in _IDENTITY_HEADER_NAMES:
        value = request.headers.get(name)
        if value is not None:
            server[_http_header_to_state_key(name)] = value

    existing_state = input_data.state if isinstance(input_data.state, dict) else {}
    existing_headers = (
        existing_state.get("headers") if isinstance(existing_state.get("headers"), dict) else {}
    )
    rest = {k: v for k, v in existing_headers.items() if k not in _IDENTITY_STATE_KEYS}
    merged_headers = {**rest, **server}
    return {"headers": merged_headers}


def _user_id_from_request(inp: RunAgentInput) -> str:
    """Resolve ADK user id from AG-UI state populated by extract_headers (x-user-id -> state.headers.user_id)."""
    if isinstance(inp.state, dict):
        headers = inp.state.get("headers")
        if isinstance(headers, dict):
            uid = headers.get("user_id")
            if uid:
                return str(uid)
    return "anonymous"


adk_middleware_agent = ADKAgent.from_app(
    mastermechanical_app,
    user_id_extractor=_user_id_from_request,
    use_in_memory_services=True,
    emit_messages_snapshot=True,
    streaming_function_call_arguments=True,
)

app = FastAPI(title="Master Mechanical AG-UI")


@app.middleware("http")
async def ag_ui_invoker_guard(request: Request, call_next):
    """Require matching X-AG-UI-Token on POST when AG_UI_INVOKER_SECRET is set."""
    expected = os.getenv("AG_UI_INVOKER_SECRET")
    if expected and request.method == "POST":
        got = request.headers.get("x-ag-ui-token")
        try:
            ok = bool(got) and secrets.compare_digest(got, expected)
        except (TypeError, ValueError):
            ok = False
        if not ok:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


_origins = os.getenv("AG_UI_CORS_ORIGINS", "http://localhost:3000").split(",")
_origins = [o.strip() for o in _origins if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=_CORS_ALLOW_METHODS,
    allow_headers=_CORS_ALLOW_HEADERS,
)

add_adk_fastapi_endpoint(
    app,
    adk_middleware_agent,
    path="/",
    extract_state_from_request=_extract_trusted_identity_headers,
)
