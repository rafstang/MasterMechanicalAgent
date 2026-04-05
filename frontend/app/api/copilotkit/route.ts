import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { auth } from "@/auth";
import type { NextRequest } from "next/server";

const serviceAdapter = new ExperimentalEmptyAdapter();

const backendUrl =
  process.env.AG_UI_BACKEND_URL?.replace(/\/?$/, "/") ?? "http://localhost:8000/";

const invokerHeaders: Record<string, string> = process.env.AG_UI_INVOKER_SECRET
  ? { "X-AG-UI-Token": process.env.AG_UI_INVOKER_SECRET }
  : {};

const runtime = new CopilotRuntime({
  agents: {
    master_mechanical_agent: new HttpAgent({
      url: backendUrl,
      headers: invokerHeaders,
    }),
  },
});

const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
  runtime,
  serviceAdapter,
  endpoint: "/api/copilotkit",
});

/**
 * Forwards CopilotKit to the AG-UI FastAPI server. Sets identity headers from the
 * verified Auth.js session only (ignores any client-supplied values).
 */
export const POST = async (req: NextRequest) => {
  const session = await auth();
  const headers = new Headers(req.headers);
  if (session?.user?.id) {
    headers.set("X-User-Id", session.user.id);
  } else {
    headers.delete("X-User-Id");
  }
  const email = session?.user?.email;
  if (email) {
    headers.set("X-User-Email", email);
  } else {
    headers.delete("X-User-Email");
  }
  const name = session?.user?.name;
  if (name) {
    headers.set("X-User-Name", name);
  } else {
    headers.delete("X-User-Name");
  }

  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    body: req.body,
    duplex: "half",
  };
  const forward = new Request(req.url, init);

  return handleRequest(forward);
};
