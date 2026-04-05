"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";

export default function Home() {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return (
      <div className="flex min-h-full flex-1 items-center justify-center bg-zinc-100 text-zinc-600">
        Loading…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-6 bg-zinc-100 px-6">
        <h1 className="text-2xl font-semibold text-zinc-900">Master Mechanical Agent</h1>
        <p className="max-w-md text-center text-zinc-600">
          Sign in with Google to chat with the HVAC assistant. Your Google account id is passed to the
          agent for session scoping.
        </p>
        <button
          type="button"
          onClick={() => signIn("google")}
          className="rounded-lg bg-zinc-900 px-6 py-3 text-white transition hover:bg-zinc-800"
        >
          Sign in with Google
        </button>
      </div>
    );
  }

  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="master_mechanical_agent">
      <div className="flex min-h-full flex-1 flex-col bg-zinc-50">
        <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-3">
          <span className="text-sm text-zinc-700">
            Signed in as <span className="font-medium">{session.user?.email ?? session.user?.name}</span>
          </span>
          <button
            type="button"
            onClick={() => signOut()}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50"
          >
            Sign out
          </button>
        </header>
        <main className="flex flex-1 flex-col items-center justify-center p-8">
          <p className="max-w-lg text-center text-zinc-600">
            Use the assistant panel to ask about HVAC or your BigQuery customer and job data. Your user id
            is sent to the agent on each request.
          </p>
        </main>
        <CopilotSidebar
          clickOutsideToClose={false}
          defaultOpen
          labels={{
            title: "Master Mechanical",
            initial:
              "You are chatting with the Master Mechanical HVAC assistant. Ask about HVAC topics or your customers, jobs, and receivables.",
          }}
        />
      </div>
    </CopilotKit>
  );
}
